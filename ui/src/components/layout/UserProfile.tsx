import React, { useState, useEffect } from 'react';
import { User, Building2 } from 'lucide-react';
import { API_BASE_URL } from '../../lib/api';

interface UserProfileProps {
  compact?: boolean;
}

export function UserProfile({ compact = false }: UserProfileProps) {
  const [user, setUser] = useState<any>(null);
  const [tenant, setTenant] = useState<any>(null);

  useEffect(() => {
    const loadUserData = () => {
      const userData = localStorage.getItem('user');
      if (userData) {
        try {
          setUser(JSON.parse(userData));
        } catch (error) {
          console.error('Error parsing user data:', error);
        }
      }
    };

    const fetchTenantData = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const response = await fetch(`${API_BASE_URL}/api/tenants/me`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const tenantData = await response.json();
          setTenant(tenantData);
        }
      } catch (error) {
        console.error('Error fetching tenant data:', error);
      }
    };

    loadUserData();
    fetchTenantData();
  }, []);

  if (!user) return null;

  const displayName = user.first_name 
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : user.email;

  if (compact) {
    return (
      <div className="flex items-center space-x-2 text-sm text-gray-300">
        <User className="h-4 w-4" />
        <span className="truncate">{displayName}</span>
      </div>
    );
  }

  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center space-x-2 text-white">
        <User className="h-4 w-4" />
        <span className="truncate font-medium">{displayName}</span>
      </div>
      {tenant && (
        <div className="flex items-center space-x-2 text-gray-300">
          <Building2 className="h-4 w-4" />
          <span className="truncate">{tenant.name}</span>
        </div>
      )}
      {user.role && (
        <div className="text-xs text-gray-400 capitalize">
          {user.role}
        </div>
      )}
    </div>
  );
} 