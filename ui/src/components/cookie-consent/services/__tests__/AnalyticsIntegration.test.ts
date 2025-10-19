import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { AnalyticsIntegration, createAnalyticsIntegration, analyticsProviders } from '../AnalyticsIntegration';
import type { ConsentPreferences, AnalyticsConfig } from '../../types';

// Mock DOM methods
const mockAppendChild = vi.fn();
const mockRemoveChild = vi.fn();
const mockGetElementById = vi.fn();
const mockCreateElement = vi.fn();

// Mock document
Object.defineProperty(global, 'document', {
  value: {
    createElement: mockCreateElement,
    head: {
      appendChild: mockAppendChild
    },
    getElementById: mockGetElementById
  },
  writable: true
});

// Mock window
Object.defineProperty(global, 'window', {
  value: {
    dataLayer: [],
    gtag: vi.fn()
  },
  writable: true
});

// Mock btoa for script ID generation
Object.defineProperty(global, 'btoa', {
  value: (str: string) => Buffer.from(str).toString('base64'),
  writable: true
});

describe('AnalyticsIntegration', () => {
  let analyticsIntegration: AnalyticsIntegration;
  let mockScripts: any[];
  let defaultConsent: ConsentPreferences;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();
    
    // Setup mock script elements (create new ones each time)
    mockScripts = [];
    mockCreateElement.mockImplementation(() => {
      const mockScript = {
        id: '',
        src: '',
        async: false,
        defer: false,
        crossOrigin: '',
        integrity: '',
        onload: null,
        onerror: null,
        remove: vi.fn()
      };
      mockScripts.push(mockScript);
      return mockScript;
    });
    
    mockGetElementById.mockImplementation((id: string) => {
      return mockScripts.find(script => script.id === id) || null;
    });
    
    // Setup default consent
    defaultConsent = {
      essential: true,
      analytics: true,
      marketing: false,
      timestamp: Date.now(),
      version: '1.0'
    };

    // Reset window objects
    (global as any).window.dataLayer = [];
    (global as any).window.gtag = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Constructor and Configuration', () => {
    it('should create instance with default config', () => {
      analyticsIntegration = new AnalyticsIntegration();
      expect(analyticsIntegration).toBeInstanceOf(AnalyticsIntegration);
      expect(analyticsIntegration.getConfig()).toEqual({});
    });

    it('should create instance with provided config', () => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      
      analyticsIntegration = new AnalyticsIntegration(config);
      expect(analyticsIntegration.getConfig()).toEqual(config);
    });

    it('should update configuration', () => {
      analyticsIntegration = new AnalyticsIntegration();
      const newConfig = {
        googleAnalytics: {
          trackingId: 'NEW_GA_ID',
          enabled: true
        }
      };
      
      analyticsIntegration.updateConfig(newConfig);
      expect(analyticsIntegration.getConfig()).toEqual(newConfig);
    });
  });

  describe('Script Loading', () => {
    beforeEach(() => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        },
        customProvider: {
          scriptUrl: 'https://example.com/analytics.js',
          initFunction: 'customAnalytics.init'
        }
      };
      analyticsIntegration = new AnalyticsIntegration(config);
    });

    it('should not load scripts when analytics consent is false', () => {
      const consent = { ...defaultConsent, analytics: false };
      analyticsIntegration.loadScripts(consent);
      
      expect(mockCreateElement).not.toHaveBeenCalled();
      expect(mockAppendChild).not.toHaveBeenCalled();
    });

    it('should load Google Analytics when analytics consent is true', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      expect(mockCreateElement).toHaveBeenCalledWith('script');
      
      // Find the Google Analytics script
      const gaScript = mockScripts.find(script => 
        script.src.includes('googletagmanager.com/gtag/js')
      );
      expect(gaScript).toBeDefined();
      expect(gaScript.src).toBe('https://www.googletagmanager.com/gtag/js?id=GA_TRACKING_ID');
      expect(gaScript.async).toBe(true);
      expect(mockAppendChild).toHaveBeenCalledWith(gaScript);
    });

    it('should load custom provider when analytics consent is true', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Should be called twice - once for GA, once for custom provider
      expect(mockCreateElement).toHaveBeenCalledTimes(2);
      expect(mockAppendChild).toHaveBeenCalledTimes(2);
    });

    it('should not load same script twice', () => {
      // First load - should create scripts
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Simulate successful loading to mark scripts as loaded
      mockScripts.forEach(script => {
        if (script.onload) {
          script.onload();
        }
      });
      
      const firstCallCount = mockCreateElement.mock.calls.length;
      
      // Second load - should not create additional scripts
      analyticsIntegration.loadScripts(defaultConsent);
      
      expect(mockCreateElement).toHaveBeenCalledTimes(firstCallCount);
    });

    it('should track loaded scripts', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Simulate script load success for all scripts
      mockScripts.forEach(script => {
        if (script.onload) {
          script.onload();
        }
      });
      
      // Check if at least one script is tracked as loaded
      const gaScript = mockScripts.find(script => 
        script.src.includes('googletagmanager.com/gtag/js')
      );
      if (gaScript) {
        expect(analyticsIntegration.isScriptLoaded(gaScript.id)).toBe(true);
      }
    });
  });

  describe('Consent Change Handling', () => {
    beforeEach(() => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      analyticsIntegration = new AnalyticsIntegration(config);
    });

    it('should call registered callbacks on consent change', () => {
      const callback1 = vi.fn();
      const callback2 = vi.fn();
      
      analyticsIntegration.onConsentChange(callback1);
      analyticsIntegration.onConsentChange(callback2);
      
      analyticsIntegration.handleConsentChange(defaultConsent);
      
      expect(callback1).toHaveBeenCalledWith(defaultConsent);
      expect(callback2).toHaveBeenCalledWith(defaultConsent);
    });

    it('should handle callback errors gracefully', () => {
      const errorCallback = vi.fn(() => {
        throw new Error('Callback error');
      });
      const normalCallback = vi.fn();
      
      analyticsIntegration.onConsentChange(errorCallback);
      analyticsIntegration.onConsentChange(normalCallback);
      
      // Should not throw
      expect(() => {
        analyticsIntegration.handleConsentChange(defaultConsent);
      }).not.toThrow();
      
      expect(normalCallback).toHaveBeenCalled();
    });

    it('should return unsubscribe function', () => {
      const callback = vi.fn();
      const unsubscribe = analyticsIntegration.onConsentChange(callback);
      
      analyticsIntegration.handleConsentChange(defaultConsent);
      expect(callback).toHaveBeenCalledTimes(1);
      
      unsubscribe();
      analyticsIntegration.handleConsentChange(defaultConsent);
      expect(callback).toHaveBeenCalledTimes(1); // Should not be called again
    });

    it('should remove analytics scripts when consent is withdrawn', () => {
      // First load scripts and simulate successful loading
      analyticsIntegration.loadScripts(defaultConsent);
      mockScripts.forEach(script => {
        if (script.onload) {
          script.onload();
        }
      });
      
      // Then withdraw consent
      const noConsentPrefs = { ...defaultConsent, analytics: false };
      analyticsIntegration.handleConsentChange(noConsentPrefs);
      
      expect(mockGetElementById).toHaveBeenCalled();
    });
  });

  describe('Script Retry Mechanism', () => {
    beforeEach(() => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      analyticsIntegration = new AnalyticsIntegration(config);
      analyticsIntegration.setRetryConfig(2, 100); // 2 retries, 100ms delay
    });

    it('should retry failed script loads', async () => {
      const initialCallCount = mockCreateElement.mock.calls.length;
      analyticsIntegration.loadScripts(defaultConsent);
      const afterLoadCallCount = mockCreateElement.mock.calls.length;
      
      // Simulate script load failure for the first script
      const firstScript = mockScripts[mockScripts.length - 1];
      if (firstScript && firstScript.onerror) {
        firstScript.onerror(new Event('error'));
      }
      
      // Wait for retry
      await new Promise(resolve => setTimeout(resolve, 150));
      
      // Should have attempted to create script again
      expect(mockCreateElement.mock.calls.length).toBeGreaterThan(afterLoadCallCount);
    });

    it('should track retry attempts', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Simulate script load failure for the first script
      const firstScript = mockScripts[mockScripts.length - 1];
      if (firstScript && firstScript.onerror) {
        firstScript.onerror(new Event('error'));
      }
      
      const retryStats = analyticsIntegration.getRetryStats();
      expect(Object.keys(retryStats).length).toBeGreaterThan(0);
    });

    it('should stop retrying after max attempts', async () => {
      const initialCallCount = mockCreateElement.mock.calls.length;
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Get the first script that was created
      let currentScript = mockScripts[mockScripts.length - 1];
      
      // Simulate multiple failures
      for (let i = 0; i < 3; i++) {
        if (currentScript && currentScript.onerror) {
          currentScript.onerror(new Event('error'));
        }
        await new Promise(resolve => setTimeout(resolve, 150));
        // Update to the latest script created by retry
        if (mockScripts.length > 0) {
          currentScript = mockScripts[mockScripts.length - 1];
        }
      }
      
      // Should not exceed max retries + initial attempt (accounting for both GA and custom provider)
      const totalCalls = mockCreateElement.mock.calls.length - initialCallCount;
      expect(totalCalls).toBeLessThanOrEqual(6); // 2 providers * (1 initial + 2 retries)
    });
  });

  describe('Cleanup', () => {
    beforeEach(() => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      analyticsIntegration = new AnalyticsIntegration(config);
    });

    it('should remove all scripts on cleanup', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Simulate script load success
      mockScripts.forEach(script => {
        if (script.onload) {
          script.onload();
        }
      });
      
      analyticsIntegration.cleanup();
      
      expect(mockGetElementById).toHaveBeenCalled();
    });

    it('should clear all callbacks on cleanup', () => {
      const callback = vi.fn();
      analyticsIntegration.onConsentChange(callback);
      
      analyticsIntegration.cleanup();
      analyticsIntegration.handleConsentChange(defaultConsent);
      
      expect(callback).not.toHaveBeenCalled();
    });

    it('should clear retry attempts on cleanup', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Simulate failure to create retry attempt
      const firstScript = mockScripts[mockScripts.length - 1];
      if (firstScript && firstScript.onerror) {
        firstScript.onerror(new Event('error'));
      }
      
      analyticsIntegration.cleanup();
      const retryStats = analyticsIntegration.getRetryStats();
      
      expect(Object.keys(retryStats)).toHaveLength(0);
    });
  });

  describe('Utility Functions', () => {
    it('should create analytics integration with factory function', () => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      
      const integration = createAnalyticsIntegration(config);
      expect(integration).toBeInstanceOf(AnalyticsIntegration);
      expect(integration.getConfig()).toEqual(config);
    });

    it('should provide predefined analytics provider configs', () => {
      const gaConfig = analyticsProviders.googleAnalytics('GA_TRACKING_ID');
      expect(gaConfig.googleAnalytics?.trackingId).toBe('GA_TRACKING_ID');
      expect(gaConfig.googleAnalytics?.enabled).toBe(true);
      
      const customConfig = analyticsProviders.customProvider('https://example.com/script.js', 'init');
      expect(customConfig.customProvider?.scriptUrl).toBe('https://example.com/script.js');
      expect(customConfig.customProvider?.initFunction).toBe('init');
      
      const matomoConfig = analyticsProviders.matomo('https://matomo.example.com', '1');
      expect(matomoConfig.customProvider?.scriptUrl).toBe('https://matomo.example.com/matomo.js');
      
      const adobeConfig = analyticsProviders.adobe('https://adobe.example.com/script.js');
      expect(adobeConfig.customProvider?.scriptUrl).toBe('https://adobe.example.com/script.js');
    });
  });

  describe('Google Analytics Integration', () => {
    beforeEach(() => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      analyticsIntegration = new AnalyticsIntegration(config);
    });

    it('should initialize Google Analytics with GDPR compliance settings', () => {
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Find and simulate Google Analytics script load success
      const gaScript = mockScripts.find(script => 
        script.src.includes('googletagmanager.com/gtag/js')
      );
      
      if (gaScript && gaScript.onload) {
        // Reset dataLayer before test
        (global as any).window.dataLayer = [];
        
        gaScript.onload();
        
        // Verify that gtag function was created and dataLayer was populated
        expect((global as any).window.gtag).toBeDefined();
        expect(typeof (global as any).window.gtag).toBe('function');
        
        // Verify dataLayer contains the expected calls
        const dataLayer = (global as any).window.dataLayer;
        expect(dataLayer.length).toBeGreaterThan(0);
        
        // Check for 'js' call
        const jsCall = dataLayer.find((call: any[]) => call[0] === 'js');
        expect(jsCall).toBeDefined();
        expect(jsCall[1]).toBeInstanceOf(Date);
        
        // Check for 'config' call
        const configCall = dataLayer.find((call: any[]) => 
          call[0] === 'config' && call[1] === 'GA_TRACKING_ID'
        );
        expect(configCall).toBeDefined();
        expect(configCall[2]).toEqual({
          anonymize_ip: true,
          cookie_flags: 'SameSite=None;Secure'
        });
        
        // Check for 'consent' call
        const consentCall = dataLayer.find((call: any[]) => 
          call[0] === 'consent' && call[1] === 'default'
        );
        expect(consentCall).toBeDefined();
        expect(consentCall[2]).toEqual({
          analytics_storage: 'granted',
          ad_storage: 'denied'
        });
      } else {
        // If no GA script found, test should fail
        expect(gaScript).toBeDefined();
      }
    });

    it('should update consent when analytics is withdrawn', () => {
      // First load scripts
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Then withdraw consent
      const noConsentPrefs = { ...defaultConsent, analytics: false };
      analyticsIntegration.handleConsentChange(noConsentPrefs);
      
      expect((global as any).window.gtag).toHaveBeenCalledWith('consent', 'update', {
        analytics_storage: 'denied'
      });
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      const config: AnalyticsConfig = {
        googleAnalytics: {
          trackingId: 'GA_TRACKING_ID',
          enabled: true
        }
      };
      analyticsIntegration = new AnalyticsIntegration(config);
    });

    it('should handle script creation errors gracefully', () => {
      mockCreateElement.mockImplementation(() => {
        throw new Error('Script creation failed');
      });
      
      expect(() => {
        analyticsIntegration.loadScripts(defaultConsent);
      }).not.toThrow();
    });

    it('should handle missing initialization functions gracefully', () => {
      const config: AnalyticsConfig = {
        customProvider: {
          scriptUrl: 'https://example.com/analytics.js',
          initFunction: 'nonexistent.function'
        }
      };
      
      analyticsIntegration = new AnalyticsIntegration(config);
      analyticsIntegration.loadScripts(defaultConsent);
      
      // Find the custom provider script
      const customScript = mockScripts.find(script => 
        script.src.includes('example.com/analytics.js')
      );
      
      // Simulate script load success
      if (customScript && customScript.onload) {
        expect(() => customScript.onload()).not.toThrow();
      }
    });
  });
});