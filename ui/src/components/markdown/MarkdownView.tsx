import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

interface MarkdownViewProps {
  source: string | null | undefined;
  className?: string;
  /** Tailwind-typography prose size ("prose-sm" by default). */
  proseSize?: 'prose-xs' | 'prose-sm' | 'prose-base' | 'prose-lg';
}

/**
 * Read-only markdown renderer. GFM enabled (tables, task lists, strikethrough,
 * autolinks). Raw HTML is not allowed — react-markdown's default escapes it,
 * so a literal `<script>` in the source renders as text.
 */
export function MarkdownView({ source, className, proseSize = 'prose-sm' }: MarkdownViewProps) {
  if (!source || !source.trim()) {
    return null;
  }
  return (
    <div
      className={cn(
        'prose dark:prose-invert max-w-none break-words',
        proseSize,
        // Tighter spacing for note-style usage
        'prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0',
        'prose-table:my-2 prose-th:py-1 prose-td:py-1',
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, href, title }) => (
            <a href={href} title={title} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
