/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  
  // Analytics
  readonly VITE_GA_MEASUREMENT_ID?: string
  
  // Marketing
  readonly VITE_GOOGLE_ADS_ID?: string
  readonly VITE_GOOGLE_ADS_CONVERSION_ID?: string
  readonly VITE_FACEBOOK_PIXEL_ID?: string
  readonly VITE_LINKEDIN_PARTNER_ID?: string
  
  // Other Analytics Providers
  readonly VITE_MIXPANEL_TOKEN?: string
  readonly VITE_HOTJAR_ID?: string
  readonly VITE_INTERCOM_APP_ID?: string
  
  // Environment
  readonly VITE_ENVIRONMENT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
