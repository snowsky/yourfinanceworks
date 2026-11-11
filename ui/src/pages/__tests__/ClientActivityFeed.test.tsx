import './authTestSetup';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ClientActivityFeed } from '@/components/clients/ClientActivityFeed';

const ITEMS = [
  { type: 'note_created', timestamp: '2026-10-01T10:00:00Z', title: 'Note', description: 'Called', actor_name: 'Sam', entity_type: 'note', entity_id: '1', metadata: {} },
  { type: 'invoice_overdue', timestamp: '2026-10-02T10:00:00Z', title: 'INV-1 is overdue', description: null, actor_name: null, entity_type: 'invoice', entity_id: '2', metadata: {} },
  { type: 'mystery', timestamp: '2026-10-03T10:00:00Z', title: 'Odd', description: null, actor_name: null, entity_type: 'x', entity_id: '3', metadata: {} },
] as never;

const setup = (props = {}) =>
  render(
    <ClientActivityFeed activity={ITEMS} newNote="" onNoteChange={vi.fn()} onAddNote={vi.fn()} {...props} />
  );

describe('ClientActivityFeed', () => {
  it('renders every label through translation keys', () => {
    setup({ onMarkContacted: vi.fn(), onCreateTaskFromActivity: vi.fn() });
    expect(screen.getByText('editClient.activity.title')).toBeTruthy();
    expect(screen.getByText('editClient.activity.markContacted')).toBeTruthy();
    expect(screen.getByText('editClient.activity.addNote')).toBeTruthy();
    expect(screen.getByPlaceholderText('editClient.activity.notePlaceholder')).toBeTruthy();
    expect(screen.getAllByText('editClient.activity.createFollowUp')).toHaveLength(2);
  });

  it('filters by type, marks the active filter, and shows the empty state', () => {
    setup();
    const tasks = screen.getByRole('button', { name: 'editClient.activity.filters.tasks' });
    expect(screen.getByRole('button', { name: 'editClient.activity.filters.all' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(tasks);
    expect(tasks.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('editClient.activity.empty')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'editClient.activity.filters.invoices' }));
    expect(screen.getByText('INV-1 is overdue')).toBeTruthy();
    expect(screen.queryByText('Odd')).toBeNull();
  });

  it('keeps the raw type as the badge for unknown activity types', () => {
    setup();
    expect(screen.getByText('mystery')).toBeTruthy();
  });

  it('only offers a follow-up for overdue, payment and note items', () => {
    const onCreate = vi.fn();
    setup({ onCreateTaskFromActivity: onCreate });
    const buttons = screen.getAllByText('editClient.activity.createFollowUp');
    fireEvent.click(buttons[0]);
    expect(onCreate).toHaveBeenCalledTimes(1);
    expect(buttons).toHaveLength(2);
  });
});
