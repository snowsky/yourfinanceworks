import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string, opts?: any) => (opts?.defaultValue as string) ?? key }),
}));
const onboardingApi = vi.hoisted(() => ({
  getSampleDataStatus: vi.fn(),
  seedSampleData: vi.fn(),
  clearSampleData: vi.fn(),
}));
vi.mock('@/lib/api', () => ({ onboardingApi }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { SampleDataBanner } from './SampleDataBanner';

describe('SampleDataBanner', () => {
  beforeEach(() => {
    onboardingApi.getSampleDataStatus.mockReset();
    onboardingApi.seedSampleData.mockReset().mockResolvedValue({});
    onboardingApi.clearSampleData.mockReset().mockResolvedValue({});
  });

  it('shows the load CTA when the tenant has no data and seeds on click', async () => {
    onboardingApi.getSampleDataStatus.mockResolvedValue({ has_sample_data: false, has_any_data: false });
    render(<SampleDataBanner />);
    const btn = await screen.findByRole('button', { name: /load example data/i });
    fireEvent.click(btn);
    await waitFor(() => expect(onboardingApi.seedSampleData).toHaveBeenCalled());
  });

  it('shows the remove affordance when sample data exists', async () => {
    onboardingApi.getSampleDataStatus.mockResolvedValue({ has_sample_data: true, has_any_data: true });
    render(<SampleDataBanner />);
    const btn = await screen.findByRole('button', { name: /remove sample data/i });
    fireEvent.click(btn);
    await waitFor(() => expect(onboardingApi.clearSampleData).toHaveBeenCalled());
  });

  it('renders nothing when there is real data and no sample data', async () => {
    onboardingApi.getSampleDataStatus.mockResolvedValue({ has_sample_data: false, has_any_data: true });
    const { container } = render(<SampleDataBanner />);
    await waitFor(() => expect(onboardingApi.getSampleDataStatus).toHaveBeenCalled());
    expect(container.querySelector('button')).toBeNull();
  });
});
