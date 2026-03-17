import { apiRequest } from './_base';
import type { User } from '@/types';

// Auth API methods
export const authApi = {
  login: (email: string, password: string) =>
    apiRequest<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }, { isLogin: true }),
  register: (userData: any) =>
    apiRequest<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    }, { isLogin: true }),
  checkOrganizationNameAvailability: (name: string) =>
    apiRequest<{ available: boolean; name: string }>(`/tenants/check-name-availability?name=${encodeURIComponent(name)}`, {
      method: 'GET',
    }),
  checkEmailAvailability: (email: string) =>
    apiRequest<{ available: boolean; email: string }>(`/auth/check-email-availability?email=${encodeURIComponent(email)}`, {
      method: 'GET',
    }),

  // Organization join request functions
  lookupOrganization: (organizationName: string) =>
    apiRequest<{ exists: boolean; tenant_id?: number; organization_name?: string; message: string }>('/organization-join/lookup', {
      method: 'POST',
      body: JSON.stringify({ organization_name: organizationName }),
    }),

  submitJoinRequest: (requestData: any) =>
    apiRequest<{ success: boolean; message: string; request_id?: number }>('/organization-join/request', {
      method: 'POST',
      body: JSON.stringify(requestData),
    }),

  // Admin functions for managing join requests
  getPendingJoinRequests: () =>
    apiRequest<any[]>('/organization-join/pending', {
      method: 'GET',
    }),

  getJoinRequestDetails: (requestId: number) =>
    apiRequest<any>(`/organization-join/${requestId}`, {
      method: 'GET',
    }),

  processJoinRequest: (requestId: number, approvalData: any) =>
    apiRequest<{ success: boolean; message: string }>(`/organization-join/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify(approvalData),
    }),
  requestPasswordReset: (email: string) =>
    apiRequest<{ message: string; success: boolean }>(`/auth/request-password-reset`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, newPassword: string) =>
    apiRequest<{ message: string; success: boolean }>(`/auth/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  changePassword: (data: any) =>
    apiRequest<{ message: string; success: boolean }>(`/auth/change-password`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateCurrentUser: (data: any) =>
    apiRequest<any>(`/auth/me`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  activateUser: (inviteId: number, activationData: { password?: string; first_name?: string; last_name?: string }) =>
    apiRequest<any>(`/auth/invites/${inviteId}/activate`, {
      method: 'POST',
      body: JSON.stringify(activationData),
    }),
  getCurrentUser: () => apiRequest<any>('/auth/me', {}, { skipTenant: true }),
  getSSOStatus: () => apiRequest<{ google: boolean; microsoft: boolean; has_sso: boolean }>('/auth/sso-status', {}, { skipTenant: true }),
  getPasswordRequirements: () => apiRequest<{ min_length: number; complexity: any; requirements: string[] }>('/auth/password-requirements', {}, { skipTenant: true }),
};

// User API methods
export const userApi = {
  getUsers: () => apiRequest<User[]>('/auth/users'),
  getUser: (id: number) => apiRequest<User>(`/auth/users/${id}`),
  updateUser: (id: number, userData: Partial<User>) =>
    apiRequest<User>(`/auth/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    }),
  deleteUser: (id: number) =>
    apiRequest<{ message: string }>(`/auth/users/${id}`, {
      method: 'DELETE',
    }),
};
