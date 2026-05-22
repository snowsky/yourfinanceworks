import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { MarkdownEditor } from '../MarkdownEditor';

// Minimal wrapper that mirrors how the component is used in real code (controlled).
function Controlled({ onChange }: { onChange: (v: string) => void }) {
  const [val, setVal] = useState('');
  return (
    <MarkdownEditor
      value={val}
      onChange={(v) => {
        setVal(v);
        onChange(v);
      }}
      placeholder="notes…"
    />
  );
}

describe('MarkdownEditor', () => {
  it('shows the textarea by default and calls onChange on typing', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Controlled onChange={onChange} />);

    const ta = screen.getByPlaceholderText('notes…');
    await user.type(ta, 'hi');
    // With proper controlled state, the cumulative value is the last call.
    expect(onChange.mock.calls.at(-1)?.[0]).toBe('hi');
  });

  it('Preview tab is disabled when there is no content', () => {
    render(<MarkdownEditor value="" onChange={() => {}} />);
    expect(screen.getByRole('tab', { name: 'Preview' })).toBeDisabled();
  });

  it('switching to Preview renders the markdown', async () => {
    const user = userEvent.setup();
    render(<MarkdownEditor value="**hi**" onChange={() => {}} />);

    await user.click(screen.getByRole('tab', { name: 'Preview' }));

    const strong = await screen.findByText('hi');
    expect(strong.tagName).toBe('STRONG');
  });
});
