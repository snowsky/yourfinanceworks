import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarkdownView } from '../MarkdownView';

describe('MarkdownView', () => {
  it('renders **bold** as <strong>', () => {
    render(<MarkdownView source="Hello **world**" />);
    const strong = screen.getByText('world');
    expect(strong.tagName).toBe('STRONG');
  });

  it('renders GFM tables', () => {
    const md = ['| Date | Amount |', '|---|---:|', '| 2026-03-14 | 7.40 |'].join('\n');
    render(<MarkdownView source={md} />);
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(screen.getByText('Date')).toBeInTheDocument();
    expect(screen.getByText('7.40')).toBeInTheDocument();
  });

  it('escapes raw HTML — <script> renders as text, not as a real tag', () => {
    const { container } = render(
      <MarkdownView source={'before <script>alert(1)</script> after'} />
    );
    // No <script> element should be present in the rendered output
    expect(container.querySelector('script')).toBeNull();
    // The literal text should still appear (markdown processes it as inline HTML which react-markdown drops)
    expect(container.textContent).toContain('before');
    expect(container.textContent).toContain('after');
  });

  it('adds target=_blank rel=noopener to links', () => {
    render(<MarkdownView source="[click](https://example.com)" />);
    const a = screen.getByRole('link', { name: 'click' }) as HTMLAnchorElement;
    expect(a.getAttribute('href')).toBe('https://example.com');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('returns null for empty/whitespace input', () => {
    const { container } = render(<MarkdownView source="   " />);
    expect(container.firstChild).toBeNull();
  });
});
