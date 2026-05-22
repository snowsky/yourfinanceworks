import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { MarkdownView } from './MarkdownView';

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  textareaClassName?: string;
  rows?: number;
  /** Hide the markdown hint shown under the editor. */
  hideHint?: boolean;
}

/**
 * Drop-in replacement for a plain notes <Textarea> that adds a "Preview" tab
 * rendering the input as markdown (GFM, no raw HTML).
 */
export function MarkdownEditor({
  value,
  onChange,
  onBlur,
  placeholder,
  disabled = false,
  className,
  textareaClassName,
  rows,
  hideHint = false,
}: MarkdownEditorProps) {
  const [tab, setTab] = useState<'write' | 'preview'>('write');
  const hasContent = !!value && !!value.trim();

  return (
    <div className={cn('w-full', className)}>
      <Tabs value={tab} onValueChange={(v) => setTab(v as 'write' | 'preview')}>
        <TabsList className="h-9">
          <TabsTrigger value="write" className="text-xs px-3 py-1.5">Write</TabsTrigger>
          <TabsTrigger value="preview" className="text-xs px-3 py-1.5" disabled={!hasContent}>
            Preview
          </TabsTrigger>
        </TabsList>
        <TabsContent value="write" className="mt-2">
          <Textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={onBlur}
            placeholder={placeholder}
            disabled={disabled}
            rows={rows}
            className={textareaClassName}
          />
          {!hideHint && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Markdown supported: <code>**bold**</code>, <code>*italic*</code>, lists, links, tables.
            </p>
          )}
        </TabsContent>
        <TabsContent value="preview" className="mt-2">
          <div className="min-h-[6rem] rounded-md border bg-background p-3">
            {hasContent ? (
              <MarkdownView source={value} />
            ) : (
              <p className="text-sm text-muted-foreground italic">Nothing to preview.</p>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
