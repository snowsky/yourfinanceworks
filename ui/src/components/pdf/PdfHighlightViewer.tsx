import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import './PdfHighlightViewer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export interface PdfHighlightViewerProps {
  /** URL (object URL or remote) of the PDF to display */
  pdfUrl: string;
  /** Transaction description text to search for in the PDF */
  searchText?: string | null;
  /** Transaction amount to help locate the right line */
  searchAmount?: number | null;
  /** Transaction date string to help locate the right line */
  searchDate?: string | null;
  /** Additional class name for the container */
  className?: string;
}

/**
 * A PDF viewer built on react-pdf (PDF.js) that supports:
 * - Rendering all pages with a text layer
 * - Searching for transaction text and highlighting matches
 * - Auto-scrolling to the matched page
 * - Responsive width fitting
 */
export function PdfHighlightViewer({
  pdfUrl,
  searchText,
  searchAmount,
  searchDate,
  className,
}: PdfHighlightViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState<number>(500);
  const [matchedPage, setMatchedPage] = useState<number | null>(null);
  const [renderedTextLayers, setRenderedTextLayers] = useState<Set<number>>(new Set());

  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------------------------------------------------------------------------
  // Responsive width via ResizeObserver
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        // Leave some padding
        setContainerWidth(Math.max(entry.contentRect.width - 28, 300));
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // ---------------------------------------------------------------------------
  // Build search tokens from the hovered transaction
  // ---------------------------------------------------------------------------
  const searchTokens = useMemo(() => {
    if (!searchText) return [];
    // Split description into meaningful tokens (>2 chars), deduplicate
    const raw = searchText
      .toLowerCase()
      .replace(/[^\w\s.-]/g, ' ')
      .split(/\s+/)
      .filter((t) => t.length > 2);
    return [...new Set(raw)];
  }, [searchText]);

  const amountStr = useMemo(() => {
    if (searchAmount == null) return null;
    return Math.abs(searchAmount).toFixed(2);
  }, [searchAmount]);

  const dateTokens = useMemo(() => {
    if (!searchDate) return [];
    // Parse YYYY-MM-DD and generate several formats to match
    const parts = searchDate.split('-');
    if (parts.length !== 3) return [searchDate];
    const [y, m, d] = parts;
    const monthNames = [
      '', 'jan', 'feb', 'mar', 'apr', 'may', 'jun',
      'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
    ];
    const mi = parseInt(m, 10);
    const di = parseInt(d, 10);
    const tokens: string[] = [
      searchDate,                                  // 2024-01-15
      `${m}/${d}/${y}`,                            // 01/15/2024
      `${di}/${mi}/${y}`,                          // 15/1/2024
      `${m}-${d}-${y}`,                            // 01-15-2024
      `${d}-${m}-${y}`,                            // 15-01-2024
      `${m}/${d}`,                                 // 01/15
      `${d}/${m}`,                                 // 15/01
    ];
    if (mi >= 1 && mi <= 12) {
      const mName = monthNames[mi];
      tokens.push(`${mName} ${di}`);               // jan 15
      tokens.push(`${di} ${mName}`);               // 15 jan
      tokens.push(`${mName} ${d}`);                // jan 15 (padded)
    }
    return tokens;
  }, [searchDate]);

  // ---------------------------------------------------------------------------
  // customTextRenderer – injects <mark> around matching tokens
  // ---------------------------------------------------------------------------
  const customTextRenderer = useCallback(
    (textItem: { str: string; itemIndex: number; pageIndex: number; pageNumber: number }) => {
      if (searchTokens.length === 0 && !amountStr && dateTokens.length === 0) {
        return textItem.str;
      }

      let result = textItem.str;
      const lowerStr = result.toLowerCase();

      // Check if this text item contains any match
      let hasMatch = false;

      // Check description tokens
      for (const token of searchTokens) {
        if (lowerStr.includes(token)) {
          hasMatch = true;
          break;
        }
      }

      // Check amount
      if (!hasMatch && amountStr && lowerStr.includes(amountStr)) {
        hasMatch = true;
      }

      // Check date tokens
      if (!hasMatch) {
        for (const dt of dateTokens) {
          if (lowerStr.includes(dt.toLowerCase())) {
            hasMatch = true;
            break;
          }
        }
      }

      if (!hasMatch) return result;

      // Escape HTML in the original string first
      const escaped = result
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      // Build a combined regex from all matching patterns
      const patterns: string[] = [];

      for (const token of searchTokens) {
        if (lowerStr.includes(token)) {
          patterns.push(escapeRegex(token));
        }
      }
      if (amountStr && lowerStr.includes(amountStr)) {
        patterns.push(escapeRegex(amountStr));
      }
      for (const dt of dateTokens) {
        if (lowerStr.includes(dt.toLowerCase())) {
          patterns.push(escapeRegex(dt));
        }
      }

      if (patterns.length === 0) return result;

      const regex = new RegExp(`(${patterns.join('|')})`, 'gi');
      return escaped.replace(regex, '<mark class="pdf-text-match">$1</mark>');
    },
    [searchTokens, amountStr, dateTokens]
  );

  // ---------------------------------------------------------------------------
  // Find the best-matching page and scroll to it
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (searchTokens.length === 0 && !amountStr && dateTokens.length === 0) {
      setMatchedPage(null);
      return;
    }

    // Debounce the search slightly
    if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
    highlightTimeoutRef.current = setTimeout(() => {
      findBestPageAndScroll();
    }, 80);

    return () => {
      if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
    };
  }, [searchTokens, amountStr, dateTokens, renderedTextLayers]);

  const findBestPageAndScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    let bestPage: number | null = null;
    let bestScore = 0;

    // Search through rendered text layer spans in the DOM
    for (let pageNum = 1; pageNum <= numPages; pageNum++) {
      const pageEl = pageRefs.current.get(pageNum);
      if (!pageEl) continue;

      const textSpans = pageEl.querySelectorAll(
        '.react-pdf__Page__textContent span'
      );
      let pageScore = 0;

      textSpans.forEach((span) => {
        const text = (span.textContent || '').toLowerCase();

        for (const token of searchTokens) {
          if (text.includes(token)) pageScore += 2;
        }
        if (amountStr && text.includes(amountStr)) pageScore += 5;
        for (const dt of dateTokens) {
          if (text.includes(dt.toLowerCase())) pageScore += 3;
        }
      });

      if (pageScore > bestScore) {
        bestScore = pageScore;
        bestPage = pageNum;
      }
    }

    setMatchedPage(bestPage);

    // Scroll to the matched page
    if (bestPage) {
      const pageEl = pageRefs.current.get(bestPage);
      if (pageEl) {
        pageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [numPages, searchTokens, amountStr, dateTokens]);

  // ---------------------------------------------------------------------------
  // Document load
  // ---------------------------------------------------------------------------
  const onDocumentLoadSuccess = useCallback(
    ({ numPages: n }: { numPages: number }) => {
      setNumPages(n);
      setRenderedTextLayers(new Set());
      setMatchedPage(null);
    },
    []
  );

  // Track when text layers are ready
  const handleTextLayerSuccess = useCallback((pageNum: number) => {
    setRenderedTextLayers((prev) => {
      const next = new Set(prev);
      next.add(pageNum);
      return next;
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div
      ref={containerRef}
      className={`pdf-highlight-viewer ${className || ''}`}
      style={{ height: '100%' }}
    >
      <Document
        file={pdfUrl}
        onLoadSuccess={onDocumentLoadSuccess}
        loading={
          <div className="pdf-loading-state">
            <div className="pdf-loading-spinner" />
            <span className="text-xs font-medium">Loading PDF…</span>
          </div>
        }
        error={
          <div className="pdf-loading-state">
            <span className="text-xs text-destructive">Failed to load PDF</span>
          </div>
        }
      >
        {Array.from({ length: numPages }, (_, i) => {
          const pageNum = i + 1;
          const isMatched = matchedPage === pageNum;

          return (
            <div
              key={pageNum}
              ref={(el) => {
                if (el) pageRefs.current.set(pageNum, el);
              }}
              className={`pdf-page-wrapper ${isMatched ? 'matched' : ''}`}
              style={{ position: 'relative' }}
            >
              {isMatched && (
                <div className="pdf-match-indicator">
                  ● Match found
                </div>
              )}
              <Page
                pageNumber={pageNum}
                width={containerWidth}
                renderTextLayer={true}
                renderAnnotationLayer={false}
                customTextRenderer={
                  searchTokens.length > 0 || amountStr || dateTokens.length > 0
                    ? customTextRenderer
                    : undefined
                }
                onRenderTextLayerSuccess={() => handleTextLayerSuccess(pageNum)}
                loading={
                  <div
                    style={{
                      width: containerWidth,
                      height: containerWidth * 1.41,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'hsl(var(--muted) / 0.3)',
                      borderRadius: 4,
                    }}
                  >
                    <div className="pdf-loading-spinner" />
                  </div>
                }
              />
            </div>
          );
        })}
      </Document>
    </div>
  );
}

/** Escape special regex characters in a string */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
