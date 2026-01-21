import { useEffect } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { APP_NAME } from '@/constants/app';

interface FaviconProps {
  logoUrl?: string;
  companyName?: string;
}

export function Favicon({ logoUrl, companyName }: FaviconProps) {
  useEffect(() => {
    const updateFavicon = () => {
      if (logoUrl) {
        // Remove all existing favicon links when using company logo
        const existingLinks = document.querySelectorAll('link[rel*="icon"]');
        existingLinks.forEach(link => link.remove());

        // Use company logo as favicon
        const link = document.createElement('link');
        link.rel = 'icon';
        link.type = 'image/x-icon';
        link.href = `${API_BASE_URL}${logoUrl}`;
        document.head.appendChild(link);

        // Also add apple-touch-icon for mobile
        const appleLink = document.createElement('link');
        appleLink.rel = 'apple-touch-icon';
        appleLink.href = `${API_BASE_URL}${logoUrl}`;
        document.head.appendChild(appleLink);
      }
      // If no logoUrl, leave the favicon from index.html alone (no flash)

      // Update document title with company name
      if (companyName) {
        document.title = `${companyName} - ${APP_NAME}`;
      } else {
        document.title = APP_NAME;
      }
    };

    updateFavicon();
  }, [logoUrl, companyName]);

  return null; // This component doesn't render anything
}