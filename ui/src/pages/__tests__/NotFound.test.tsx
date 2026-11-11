import './authTestSetup';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import NotFound from '../NotFound';

const renderAt = () =>
  render(
    <MemoryRouter initialEntries={['/start', '/no/such/page']} initialIndex={1}>
      <Routes>
        <Route path="/start" element={<div>START</div>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </MemoryRouter>,
  );

describe('404 page', () => {
  it('shows the brand, a translated message and the missing path', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    renderAt();
    expect(screen.getByText('YourFinanceWORKS')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'notFound.title' })).toBeInTheDocument();
    expect(screen.getByText('/no/such/page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'notFound.home' })).toHaveAttribute('href', '/');
  });

  it('goes back to the previous page', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    renderAt();
    fireEvent.click(screen.getByRole('button', { name: 'notFound.back' }));
    expect(screen.getByText('START')).toBeInTheDocument();
  });
});
