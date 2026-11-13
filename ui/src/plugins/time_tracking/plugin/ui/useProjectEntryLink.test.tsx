import { renderHook, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useProjectEntryLink } from './useProjectEntryLink';

afterEach(() => { cleanup(); document.body.innerHTML = ''; });

it('selects the time tab and waits for the linked row before scrolling', () => {
  const select = vi.fn();
  const row = document.createElement('div');
  row.id = 'time-entry-42';
  row.scrollIntoView = vi.fn();
  const { rerender } = renderHook(({ entries, tab }) => useProjectEntryLink('?time_entry_id=42', entries, tab, select),
    { initialProps: { entries: [] as { id: number }[], tab: 'Overview' } });
  expect(select).toHaveBeenCalledOnce();
  document.body.append(row);
  rerender({ entries: [{ id: 42 }], tab: 'Time Entries' });
  expect(row.scrollIntoView).toHaveBeenCalledWith({ block: 'center' });
});

it('handles a new linked entry on an already mounted project and ignores malformed IDs', () => {
  const select = vi.fn();
  const { rerender } = renderHook(({ search }) => useProjectEntryLink(search, [], 'Overview', select),
    { initialProps: { search: '' } });
  rerender({ search: '?time_entry_id=12' });
  expect(select).toHaveBeenCalledOnce();
  rerender({ search: '?time_entry_id=invalid' });
  expect(select).toHaveBeenCalledOnce();
});
