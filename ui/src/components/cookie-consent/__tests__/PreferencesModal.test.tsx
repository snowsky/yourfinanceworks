import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { PreferencesModal } from '../PreferencesModal';
import type { PreferencesModalProps, ConsentPreferences } from '../types';

describe('PreferencesModal', () => {
  const mockPreferences: ConsentPreferences = {
    essential: true,
    analytics: false,
    marketing: false,
    timestamp: Date.now(),
    version: '1.0.0'
  };

  const defaultProps: PreferencesModalProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSave: vi.fn(),
    currentPreferences: mockPreferences,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal when isOpen is true', () => {
    render(<PreferencesModal {...defaultProps} />);
    expect(screen.getByTestId('preferences-modal')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    render(<PreferencesModal {...defaultProps} isOpen={false} />);
    expect(screen.queryByTestId('preferences-modal')).not.toBeInTheDocument();
  });

  it('displays cookie categories', () => {
    render(<PreferencesModal {...defaultProps} />);
    expect(screen.getByText('Essential Cookies')).toBeInTheDocument();
    expect(screen.getByText('Analytics Cookies')).toBeInTheDocument();
    expect(screen.getByText('Marketing Cookies')).toBeInTheDocument();
  });

  it('calls onSave when save button is clicked', () => {
    const onSave = vi.fn();
    render(<PreferencesModal {...defaultProps} onSave={onSave} />);
    
    const saveButton = screen.getByRole('button', { name: /save preferences/i });
    fireEvent.click(saveButton);
    
    expect(onSave).toHaveBeenCalled();
  });

  it('calls onClose when cancel button is clicked', () => {
    const onClose = vi.fn();
    render(<PreferencesModal {...defaultProps} onClose={onClose} />);
    
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);
    
    expect(onClose).toHaveBeenCalled();
  });

  it('closes modal when Escape key is pressed', () => {
    const onClose = vi.fn();
    render(<PreferencesModal {...defaultProps} onClose={onClose} />);
    
    fireEvent.keyDown(document, { key: 'Escape' });
    
    expect(onClose).toHaveBeenCalled();
  });
});