import { apiRequest } from './_base';

// ============================================================================
// Export Destination API Types
// ============================================================================

export interface ExportDestination {
  id: number;
  tenant_id: number;
  name: string;
  destination_type: 's3' | 'azure' | 'gcs' | 'google_drive' | 'local';
  is_active: boolean;
  is_default: boolean;
  config?: Record<string, any>;
  masked_credentials?: Record<string, string>;
  last_test_at?: string;
  last_test_success?: boolean;
  last_test_error?: string;
  created_at: string;
  updated_at?: string;
  created_by?: number;
  testable?: boolean;
}

export interface ExportDestinationCreate {
  name: string;
  destination_type: 's3' | 'azure' | 'gcs' | 'google_drive' | 'local';
  credentials: Record<string, any>;
  config?: Record<string, any>;
  is_default?: boolean;
}

export interface ExportDestinationUpdate {
  name?: string;
  credentials?: Record<string, any>;
  config?: Record<string, any>;
  is_active?: boolean;
  is_default?: boolean;
}

export interface ExportDestinationTestResult {
  success: boolean;
  message: string;
  error_details?: string;
  tested_at: string;
}

// ============================================================================
// Export Destination API Methods
// ============================================================================

export const exportDestinationApi = {
  // Get all export destinations for the current tenant
  getDestinations: () =>
    apiRequest<ExportDestination[]>('/export-destinations/'),

  // Get a specific export destination
  getDestination: (id: number) =>
    apiRequest<ExportDestination>(`/export-destinations/${id}`),

  // Create a new export destination
  createDestination: (data: ExportDestinationCreate) =>
    apiRequest<ExportDestination>('/export-destinations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Update an export destination
  updateDestination: (id: number, data: ExportDestinationUpdate) =>
    apiRequest<ExportDestination>(`/export-destinations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete an export destination
  deleteDestination: (id: number) =>
    apiRequest<{ message: string }>(`/export-destinations/${id}`, {
      method: 'DELETE',
    }),

  // Test connection to an export destination
  testConnection: (id: number) =>
    apiRequest<ExportDestinationTestResult>(`/export-destinations/${id}/test`, {
      method: 'POST',
    }),
};
