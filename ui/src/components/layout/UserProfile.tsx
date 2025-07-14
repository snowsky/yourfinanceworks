import React from 'react';
import { User, Building2, MapPin } from 'lucide-react';

export function UserProfile({ companyName, companyAddress, companyLogo }: { 
  companyName: string, 
  companyAddress?: string,
  companyLogo?: string 
}) {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  
  // Construct full logo URL if logo path is provided
  const logoUrl = companyLogo ? `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${companyLogo}` : null;
  
  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center space-x-2 text-white">
        <User className="h-4 w-4" />
        <span className="truncate font-medium">{user?.first_name || user?.name || 'User'}</span>
      </div>
      <div className="flex items-center space-x-2 text-gray-300">
        {logoUrl ? (
          <img 
            src={logoUrl} 
            alt="Company Logo" 
            className="h-4 w-4 object-contain rounded"
            onError={(e) => {
              console.error('Failed to load logo in sidebar:', e);
              e.currentTarget.style.display = 'none';
            }}
          />
        ) : (
          <Building2 className="h-4 w-4" />
        )}
        <span className="truncate">{companyName}</span>
      </div>
      {companyAddress && companyAddress.trim() !== '' && (
        <div className="flex items-center space-x-2 text-gray-400 text-xs">
          <MapPin className="h-4 w-4" />
          <span className="truncate">{companyAddress}</span>
        </div>
      )}
    </div>
  );
} 