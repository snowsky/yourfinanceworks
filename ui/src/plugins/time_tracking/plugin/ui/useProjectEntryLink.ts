import { useEffect } from 'react';

/** Locate a linked entry after both its tab and asynchronously loaded row exist. */
export function useProjectEntryLink(
  search: string,
  entries: ReadonlyArray<{ id: number }>,
  activeTab: string,
  selectTimeEntries: () => void,
) {
  const entryId = new URLSearchParams(search).get('time_entry_id');
  const validEntryId = entryId && /^[1-9]\d*$/.test(entryId) ? entryId : null;

  useEffect(() => {
    if (validEntryId) selectTimeEntries();
  }, [validEntryId, selectTimeEntries]);

  useEffect(() => {
    if (validEntryId && activeTab === 'Time Entries' && entries.some(entry => String(entry.id) === validEntryId)) {
      document.getElementById(`time-entry-${validEntryId}`)?.scrollIntoView?.({ block: 'center' });
    }
  }, [validEntryId, activeTab, entries]);
}
