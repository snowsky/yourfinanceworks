import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { Building, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { getCurrentUser } from "@/utils/auth";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useTranslation } from 'react-i18next';

export function OrganizationSwitcher() {
  const { t } = useTranslation();
  const location = useLocation();
  const queryClient = useQueryClient();
  const user = getCurrentUser();

  const { data: userOrganizations = [], isLoading: orgsLoading } = useOrganizations();
  const [currentOrgId, setCurrentOrgId] = useState(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('selected_tenant_id');
      if (stored) return stored;
    }
    return user?.tenant_id?.toString() || '';
  });
  const [isSwitchingOrg, setIsSwitchingOrg] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [buttonRect, setButtonRect] = useState<DOMRect | null>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // Check if click is outside both button AND dropdown content
      if (
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  const handleOrganizationSwitch = useCallback(async (orgId: string) => {
    if (orgId === currentOrgId) {
      setShowDropdown(false);
      return;
    }

    const selectedOrg = userOrganizations.find(org => org.id.toString() === orgId);
    const orgName = selectedOrg?.name || `Organization ${orgId}`;
    const userHomeTenantId = user?.tenant_id?.toString();
    const isSwitchingAwayFromHome = currentOrgId === userHomeTenantId && orgId !== userHomeTenantId;

    setIsSwitchingOrg(true);
    setShowDropdown(false);

    try {
      toast.loading(`Switching to ${orgName}...`, { id: 'org-switch' });

      localStorage.setItem('selected_tenant_id', orgId);
      setCurrentOrgId(orgId);

      // Clear caches
      try {
        localStorage.removeItem('react-query-offline-cache');
      } catch (e) {
        console.error('Error clearing cache:', e);
      }

      try {
        queryClient.clear();
        queryClient.invalidateQueries();
      } catch (e) {
        console.error('Error invalidating queries:', e);
      }

      try {
        sessionStorage.clear();
      } catch (e) {
        console.error('Error clearing session storage:', e);
      }

      toast.success(`Switched to ${orgName}`, { id: 'org-switch' });

      // Redirect to home if switching away from restricted route
      const restrictedRoutes = ['/super-admin'];
      const currentPath = location.pathname;

      if (isSwitchingAwayFromHome && restrictedRoutes.some(route => currentPath.startsWith(route))) {
        window.location.href = '/';
      } else {
        setTimeout(() => {
          window.location.reload();
        }, 100);
      }
    } catch (error) {
      console.error('Error during organization switch:', error);
      toast.error('Failed to switch organization', { id: 'org-switch' });
      setIsSwitchingOrg(false);
      setShowDropdown(true);
    }
  }, [currentOrgId, userOrganizations, user?.tenant_id, queryClient, location.pathname]);

  // Only hide if we're still loading and have no data
  if (userOrganizations.length === 0 && orgsLoading) {
    return null;
  }

  // If there's an error or no organizations at all, still show the component
  if (userOrganizations.length === 0) {
    return null;
  }

  const currentOrg = userOrganizations.find(org => org.id.toString() === currentOrgId);

  return (
    <div className="space-y-3">
      <div className="px-3">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          {t('common.organization')} {userOrganizations.length > 1 ? `(${userOrganizations.length} ${t('common.available')})` : ''}
        </h3>
      </div>
      <div className="px-3 relative">
        <button
          ref={buttonRef}
          onClick={() => {
            setShowDropdown(!showDropdown);
            if (buttonRef.current) {
              setButtonRect(buttonRef.current.getBoundingClientRect());
            }
          }}
          disabled={isSwitchingOrg}
          className="w-full bg-slate-800/30 border border-slate-700/30 text-white hover:bg-slate-700/30 rounded-lg backdrop-blur-sm p-3 flex items-center justify-between gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-2">
            <Building className="w-4 h-4 text-slate-300" />
            <span className="text-sm font-medium">
              {isSwitchingOrg ? 'Switching...' : (currentOrg?.name || 'Select organization')}
            </span>
          </div>
          <ChevronDown className={`w-4 h-4 transition-transform ${showDropdown ? 'rotate-180' : ''}`} />
        </button>

        {showDropdown && buttonRect && createPortal(
          <div
            ref={dropdownRef}
            className="fixed bg-slate-800 border border-slate-700/30 rounded-lg shadow-lg z-50 backdrop-blur-sm"
            style={{
              top: `${buttonRect.bottom + 8}px`,
              left: `${buttonRect.left}px`,
              width: `${buttonRect.width}px`,
            }}
          >
            {userOrganizations.length === 0 ? (
              <div className="px-4 py-2.5 text-sm text-slate-400">
                No organizations available
              </div>
            ) : (
              userOrganizations.sort((a, b) => a.name.localeCompare(b.name)).map((org) => (
                <button
                  key={org.id}
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleOrganizationSwitch(org.id.toString());
                  }}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors first:rounded-t-lg last:rounded-b-lg flex items-center justify-between cursor-pointer"
                >
                  <span>
                    {org.name}
                    {org.id === user?.tenant_id && (
                      <span className="text-xs text-blue-500 ml-2">(Home)</span>
                    )}
                  </span>
                  {org.id.toString() === currentOrgId && (
                    <span className="text-xs text-green-500">✓</span>
                  )}
                </button>
              ))
            )}
          </div>,
          document.body
        )}
      </div>
    </div>
  );
}
