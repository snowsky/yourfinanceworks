import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import './PdfHighlightViewer.css';
// Import the worker as a bundled URL (Vite ?url import — no CDN dependency)
import PdfjsWorkerUrl from 'pdfjs-dist/build/pdf.worker.mjs?url';

// Configure PDF.js worker from the locally bundled file
pdfjs.GlobalWorkerOptions.workerSrc = PdfjsWorkerUrl;

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
  // Build search data from the hovered transaction
  // ---------------------------------------------------------------------------

  /**
   * The full trimmed phrase — primary highlight target.
   * e.g. "SHOPIFY INC ACH"
   */
  const searchPhrase = useMemo(() =>
    searchText ? searchText.trim() : null
  , [searchText]);

  /**
   * All words (> 3 chars) used only for page-level scoring — never for highlight.
   */
  const scoringTokens = useMemo(() => {
    if (!searchText) return [];
    return [
      ...new Set(
        searchText
          .toLowerCase()
          .replace(/[^\w\s]/g, ' ')
          .split(/\s+/)
          .filter((w) => w.length > 3)
      ),
    ];
  }, [searchText]);

  const amountStr = useMemo(() => {
    if (searchAmount == null) return null;
    return Math.abs(searchAmount).toFixed(2);
  }, [searchAmount]);

  const dateTokens = useMemo(() => {
    if (!searchDate) return [];
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
      searchDate,
      `${m}/${d}/${y}`,
      `${di}/${mi}/${y}`,
      `${m}-${d}-${y}`,
      `${d}-${m}-${y}`,
      `${m}/${d}`,
      `${d}/${m}`,
    ];
    if (mi >= 1 && mi <= 12) {
      const mName = monthNames[mi];
      tokens.push(`${mName} ${di}`);
      tokens.push(`${di} ${mName}`);
      tokens.push(`${mName} ${d}`);
    }
    return tokens;
  }, [searchDate]);

  const hasAnySearch = !!(searchPhrase || amountStr || dateTokens.length > 0);

  // ---------------------------------------------------------------------------
  // customTextRenderer – three-tier phrase-first matching
  //
  // Priority:
  //  1. Full phrase match in this span          → highlight entire phrase
  //  2. Amount match                            → highlight amount
  //  3. Date format match                       → highlight date
  //
  // Intentionally NOT matching individual short words ("INC", "ACH") in
  // isolation — that's handled by the page-scoring logic only.
  // ---------------------------------------------------------------------------
  const customTextRenderer = useCallback(
    (textItem: { str: string; itemIndex: number; pageIndex: number; pageNumber: number }) => {
      const str = textItem.str;
      const lowerStr = str.toLowerCase();
      const escaped = escapeHtml(str);
      if (!hasAnySearch) return escaped;

      // Tier 1: full phrase
      if (searchPhrase && lowerStr.includes(searchPhrase.toLowerCase())) {
        const regex = new RegExp(`(${escapeRegex(searchPhrase)})`, 'gi');
        return escaped.replace(regex, '<mark class="pdf-text-match">$1</mark>');
      }

      // Tier 2: amount
      if (amountStr && lowerStr.includes(amountStr)) {
        const regex = new RegExp(`(${escapeRegex(amountStr)})`, 'gi');
        return escaped.replace(regex, '<mark class="pdf-text-match">$1</mark>');
      }

      // Tier 3: date formats
      for (const dt of dateTokens) {
        if (lowerStr.includes(dt.toLowerCase())) {
          const regex = new RegExp(`(${escapeRegex(dt)})`, 'gi');
          return escaped.replace(regex, '<mark class="pdf-text-match">$1</mark>');
        }
      }

      return escaped;
    },
    [hasAnySearch, searchPhrase, amountStr, dateTokens]
  );

  const findBestPageAndScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    let bestPage: number | null = null;
    let bestScore = 0;

    for (let pageNum = 1; pageNum <= numPages; pageNum++) {
      const pageEl = pageRefs.current.get(pageNum);
      if (!pageEl) continue;

      const textSpans = pageEl.querySelectorAll(
        '.react-pdf__Page__textContent span'
      );
      let pageScore = 0;

      // Collect all text on this page for phrase matching
      const allText = Array.from(textSpans)
        .map((s) => s.textContent || '')
        .join(' ')
        .toLowerCase();

      // Full phrase match is highest priority (score 10)
      if (searchPhrase && allText.includes(searchPhrase.toLowerCase())) {
        pageScore += 10;
      }

      // Individual scoring tokens (for partial matches across spans)
      for (const token of scoringTokens) {
        if (allText.includes(token)) pageScore += 2;
      }

      // Amount is very distinctive
      if (amountStr && allText.includes(amountStr)) pageScore += 8;

      // Date formats
      for (const dt of dateTokens) {
        if (allText.includes(dt.toLowerCase())) pageScore += 4;
      }

      if (pageScore > bestScore) {
        bestScore = pageScore;
        bestPage = pageNum;
      }
    }

    setMatchedPage(bestPage);

    if (bestPage) {
      const pageEl = pageRefs.current.get(bestPage);
      if (pageEl) {
        pageEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [numPages, searchPhrase, scoringTokens, amountStr, dateTokens]);

  // ---------------------------------------------------------------------------
  // Find the best-matching page and scroll to it
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!hasAnySearch) {
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
  }, [hasAnySearch, renderedTextLayers, findBestPageAndScroll]);

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
                customTextRenderer={hasAnySearch ? customTextRenderer : undefined}
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

/** Escape HTML special characters */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
