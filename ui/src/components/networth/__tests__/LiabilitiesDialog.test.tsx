import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { LiabilityResponse } from '@/lib/api/networth';

const createLiability = vi.fn();
const updateLiability = vi.fn();
vi.mock('@/lib/api/networth', () => ({
  networthApi: {
    listLiabilities: () => Promise.resolve([]),
    createLiability: (...a: unknown[]) => createLiability(...a),
    updateLiability: (...a: unknown[]) => updateLiability(...a),
    deleteLiability: vi.fn(),
  },
}));

import { LiabilitiesDialog } from '../LiabilitiesDialog';

const sample: LiabilityResponse = {
  id: 7,
  name: 'Car loan',
  kind: 'loan',
  balance: 12000,
  currency: 'USD',
  interest_rate: 4.5,
  notes: 'Toyota',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

beforeEach(() => {
  createLiability.mockReset().mockResolvedValue(sample);
  updateLiability.mockReset().mockResolvedValue(sample);
});

describe('LiabilitiesDialog', () => {
  it('edit mode prefills and saves via updateLiability with interest_rate + notes', async () => {
    render(<LiabilitiesDialog open liability={sample} onClose={() => {}} />);
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Car loan');
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(updateLiability).toHaveBeenCalledTimes(1));
    const [id, body] = updateLiability.mock.calls[0];
    expect(id).toBe(7);
    expect(body).toMatchObject({ name: 'Car loan', interest_rate: 4.5, notes: 'Toyota' });
    expect(createLiability).not.toHaveBeenCalled();
  });

  it('add mode (no liability) creates via createLiability', async () => {
    render(<LiabilitiesDialog open onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New card' } });
    fireEvent.change(screen.getByLabelText('Balance'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: /add liability/i }));
    await waitFor(() => expect(createLiability).toHaveBeenCalledTimes(1));
    expect(createLiability.mock.calls[0][0]).toMatchObject({ name: 'New card', balance: 500 });
  });
});
