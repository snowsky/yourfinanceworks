import React, { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'

// Mock providers for testing
const mockFeatureContext = {
  features: {},
  hasFeature: () => true,
  isFeatureEnabled: () => true,
  isFeatureExpired: () => false,
  loading: false,
  isLoading: false,
  refreshFeatures: vi.fn(),
  refetch: vi.fn(),
  licenseStatus: { isValid: true, features: [] },
}

const mockI18n = {
  t: (key: string) => key,
  language: 'en',
}

// Create mock contexts
vi.mock('../contexts/FeatureContext', () => ({
  FeatureProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useFeatures: () => mockFeatureContext,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: any) => options?.defaultValue || key,
    i18n: {
      language: 'en',
      changeLanguage: vi.fn(),
    }
  }),
  I18nextProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

// Re-export everything
export * from '@testing-library/react'

// Create QueryClient for testing
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
    mutations: {
      retry: false,
    },
  },
})

// Custom render function with all providers
const renderWithProviders = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => {
  const testQueryClient = createTestQueryClient()

  const AllTheProviders = ({ children }: { children: ReactNode }) => {
    return (
      <QueryClientProvider client={testQueryClient}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  return render(ui, { wrapper: AllTheProviders, ...options })
}

// Override render with our provider-wrapped version
export { renderWithProviders as render }
