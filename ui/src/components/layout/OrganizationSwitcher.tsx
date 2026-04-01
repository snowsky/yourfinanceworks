import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { Building, ChevronDown, Check, ChevronsUpDown, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { getCurrentUser } from "@/utils/auth";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useTranslation } from 'react-i18next';
import { settingsApi, API_BASE_URL } from "@/lib/api";

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

  // Fetch settings to get the company logo
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    staleTime: 1000 * 60 * 60, // 1 hour
    enabled: true,
  });

  const companyLogoUrl = settings?.company_info?.logo;

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
      window.dispatchEvent(new CustomEvent('org-switched', { detail: { orgId } }));

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

  // If there's an error or no organizations at all, still show the component but simplified
  const currentOrg = userOrganizations.find(org => org.id.toString() === currentOrgId);
  // Prefer settings company name (user-editable) over the org registration name
  const currentOrgName = settings?.company_info?.name || currentOrg?.name || 'InvoiceApp';

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => {
          setShowDropdown(!showDropdown);
          if (buttonRef.current) {
            setButtonRect(buttonRef.current.getBoundingClientRect());
          }
        }}
        disabled={isSwitchingOrg}
        className={`w-full group flex items-center gap-3 p-2 rounded-xl transition-all duration-200 
          ${showDropdown ? 'bg-slate-800/60 ring-2 ring-blue-500/20' : 'hover:bg-slate-800/40'}
          ${isSwitchingOrg ? 'cursor-default' : 'cursor-pointer'}
        `}
      >
        {/* Logo container */}
        <div className="flex-shrink-0 h-10 w-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg ring-1 ring-white/10 overflow-hidden">
          {companyLogoUrl ? (
            <img
              src={companyLogoUrl.startsWith('http') ? companyLogoUrl : `${API_BASE_URL}${companyLogoUrl}`}
              alt={`${currentOrgName} Logo`}
              className="h-full w-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
                e.currentTarget.parentElement?.classList.add('flex', 'items-center', 'justify-center');
                // Insert icon if image fails
                const icon = document.createElement('div');
                icon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-building text-white"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>';
                e.currentTarget.parentElement?.appendChild(icon.firstChild!);
              }}
            />
          ) : (
            <Building className="h-5 w-5 text-white" />
          )}
        </div>

        {/* Text container */}
        <div className="flex-1 min-w-0 flex flex-col items-start gap-0.5">
          <span className="text-sm font-bold text-white truncate w-full text-left leading-tight">
            {isSwitchingOrg ? 'Switching...' : currentOrgName}
          </span>
          <span className="text-xs text-slate-400 font-medium truncate w-full text-left">
            {userOrganizations.length > 1 ? 'Switch Organization' : 'YourFinanceWORKS'}
          </span>
        </div>

        {/* Chevron - Always visible to indicate this is a dropdown/menu */}
        <ChevronsUpDown className="h-4 w-4 text-slate-500 group-hover:text-slate-300 transition-colors" />
      </button>

      {showDropdown && buttonRect && createPortal(
        <div
          ref={dropdownRef}
          className="fixed bg-slate-900/95 border border-slate-700/50 rounded-xl shadow-2xl z-[100] backdrop-blur-md overflow-hidden ring-1 ring-white/10"
          style={{
            top: `${buttonRect.bottom + 6}px`,
            left: `${buttonRect.left}px`,
            width: `${buttonRect.width}px`,
            minWidth: '240px'
          }}
        >
          <div className="p-2 space-y-1 max-h-[300px] overflow-y-auto custom-scrollbar">
            <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Organizations
            </div>
            {userOrganizations.map((org) => (
              <button
                key={org.id}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleOrganizationSwitch(org.id.toString());
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all
                  ${org.id.toString() === currentOrgId
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-900/20'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'}
                `}
              >
                <div className={`p-1.5 rounded-md ${org.id.toString() === currentOrgId ? 'bg-white/20' : 'bg-slate-800'}`}>
                  <Building className="h-4 w-4" />
                </div>
                <span className="flex-1 text-left truncate font-medium">{org.name}</span>
                {org.id.toString() === currentOrgId && (
                  <Check className="h-4 w-4" />
                )}
              </button>
            ))}
          </div>
          {/* Optional: Add 'Create Organization' or similar action here if needed in future */}
        </div>,
        document.body
      )}
    </>
  );
}

