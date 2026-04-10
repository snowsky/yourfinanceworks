import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { pluginApi } from '@/lib/api/plugins';
import { PluginAuth } from '@/pages/PluginAuth';
import { PluginPaywall } from '@/pages/PluginPaywall';
import { apiRequest } from '@/lib/api/_base';
import { toast } from 'sonner';
import { LogOut, User, Settings as SettingsIcon, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface PublicAccessConfig {
  enabled: boolean;
  require_login: boolean;
  stripe_price_id?: string | null;
  free_clicks: number;
  show_sidebar: boolean;
  show_header: boolean;
  public_page: { path: string; label: string; ui_entry?: string } | null;
}

interface PaywallStatus {
  is_paid: boolean;
  usage_count: number;
  free_clicks: number;
  trial_limit_reached: boolean;
}

interface Props {
  pluginId: string;
  /** For in-process plugins: pass children. */
  children?: React.ReactNode;
  /** For sidecar plugins: pass the iframe URL directly. */
  iframeUrl?: string;
}

export function PublicPluginWrapper({ pluginId, children, iframeUrl }: Props) {
  const location = useLocation();
  const [config, setConfig] = useState<PublicAccessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [status, setStatus] = useState<PaywallStatus | null>(null);
  const [incrementing, setIncrementing] = useState(false);
  const [pluginUserData, setPluginUserData] = useState<any>(null);
  
  const searchParams = new URLSearchParams(location.search);
  const explicitTenantId = searchParams.get('t') || undefined;
  
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    pluginApi
      .getPluginPublicConfig(pluginId, explicitTenantId)
      .then((data) => {
        setConfig(data);
        checkAccess(data);
      })
      .catch(() => {
        setError('Could not load page configuration.');
        setLoading(false);
      });
  }, [pluginId, explicitTenantId]);

  const checkAccess = async (cfg: PublicAccessConfig) => {
    if (!cfg.enabled) {
      setLoading(false);
      return;
    }

    if (cfg.require_login) {
      const tokenKey = `plugin_token_${pluginId}`;
      const tokenStr = localStorage.getItem(tokenKey);
      if (!tokenStr) {
        setNeedsAuth(true);
        setLoading(false);
        return;
      }
      
      const tokenData = JSON.parse(tokenStr);
      setPluginUserData(tokenData.user);

      if (cfg.stripe_price_id) {
        try {
          const res = await apiRequest<PaywallStatus>(`/plugins/${pluginId}/public-paywall/status`, {
            method: 'POST',
            body: JSON.stringify({
               tenant_id: parseInt(explicitTenantId || String(tokenData.tenant_id), 10),
               plugin_user_id: tokenData.user.id
            })
          });
          setStatus(res);
        } catch (err) {
          console.error("Paywall check failed", err);
        }
      }
    }
    setLoading(false);
  };

  const handleLogout = () => {
    const tokenKey = `plugin_token_${pluginId}`;
    localStorage.removeItem(tokenKey);
    window.location.reload();
  };

  const handleIncrementUsage = useCallback(async () => {
    if (!status || status.is_paid || incrementing) return;
    
    const tokenKey = `plugin_token_${pluginId}`;
    const tokenStr = localStorage.getItem(tokenKey);
    if (!tokenStr) return;
    const tokenData = JSON.parse(tokenStr);

    setIncrementing(true);
    try {
      const res = await apiRequest<{ usage_count: number }>(`/plugins/${pluginId}/public-paywall/increment-usage`, {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: parseInt(explicitTenantId || String(tokenData.tenant_id), 10),
          plugin_user_id: tokenData.user.id
        })
      });
      
      const newUsage = res.usage_count;
      setStatus(prev => prev ? ({
        ...prev, 
        usage_count: newUsage,
        trial_limit_reached: prev.free_clicks > 0 && newUsage >= prev.free_clicks
      }) : null);
    } catch (err) {
      console.error("Failed to increment usage", err);
    } finally {
      // Small debounce
      setTimeout(() => setIncrementing(false), 500);
    }
  }, [pluginId, explicitTenantId, status, incrementing]);

  // Handle clicks on In-process plugins
  const handleWrapperClick = () => {
    handleIncrementUsage();
  };

  // Handle Focus (clicks) on Sidecar iframes
  useEffect(() => {
    const handleBlur = () => {
      if (document.activeElement === iframeRef.current) {
        handleIncrementUsage();
      }
    };
    window.addEventListener('blur', handleBlur);
    return () => window.removeEventListener('blur', handleBlur);
  }, [handleIncrementUsage]);

  const handleAuthenticated = () => {
     setNeedsAuth(false);
     setLoading(true);
     if (config) {
       checkAccess(config);
     }
  };

  const handleModalOpenChange = (open: boolean) => {
    // Prevent closing if limit reached and not paid
    if (!open && status?.trial_limit_reached && !status?.is_paid) {
       toast.error("Please upgrade to continue using this plugin.");
       return;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-sm text-muted-foreground animate-pulse">Loading plugin...</div>
      </div>
    );
  }

  if (error) {
    return <UnavailableMessage message={error} />;
  }

  if (!config?.enabled) {
    return <UnavailableMessage message="This page is not publicly available." />;
  }

  if (needsAuth) {
    return <PluginAuth pluginId={pluginId} tenantId={explicitTenantId} onAuthenticated={handleAuthenticated} />;
  }

  const resolvedIframeUrl = iframeUrl ?? config.public_page?.ui_entry ?? undefined;
  
  const UserMenu = () => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full">
          <User className="h-5 w-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">{pluginUserData?.email || 'Plugin User'}</p>
            <p className="text-xs leading-none text-muted-foreground">
              {pluginId} access
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => toast.info("Settings feature coming soon.")}>
          <SettingsIcon className="mr-2 h-4 w-4" />
          <span>Settings</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
          <LogOut className="mr-2 h-4 w-4" />
          <span>Log out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      {config.show_sidebar && (
        <aside className="w-64 border-r bg-muted/30 flex flex-col p-4 shrink-0 transition-all duration-300">
          <div className="flex items-center gap-2 mb-8 px-2 font-bold text-lg">
             <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground">
                {pluginId.charAt(0).toUpperCase()}
             </div>
             <span className="truncate capitalize">{pluginId.replace('-', ' ')}</span>
          </div>
          
          <nav className="flex-1 space-y-1">
             <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
               Menu
             </div>
             <Button variant="ghost" className="w-full justify-start gap-3 bg-muted/50 border-l-2 border-primary rounded-none h-10 px-3">
                <Menu className="h-4 w-4" />
                Main Page
             </Button>
          </nav>
          
          <div className="mt-auto border-t pt-4 space-y-2">
             <div className="flex items-center gap-3 px-2 py-1">
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                   <User className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                   <p className="text-xs font-medium truncate">{pluginUserData?.email || 'User'}</p>
                   <p className="text-[10px] text-muted-foreground">Plugin access</p>
                </div>
             </div>
             
             <Button variant="ghost" className="w-full justify-start gap-3 h-9 px-2 text-muted-foreground hover:text-foreground" onClick={() => toast.info("Settings feature coming soon.")}>
                <SettingsIcon className="h-4 w-4" />
                <span className="text-xs">Settings</span>
             </Button>
             
             <Button variant="ghost" className="w-full justify-start gap-3 h-9 px-2 text-destructive hover:text-destructive hover:bg-destructive/10" onClick={handleLogout}>
                <LogOut className="h-4 w-4" />
                <span className="text-xs font-medium">Log out</span>
             </Button>
          </div>
        </aside>
      )}

      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        {config.show_header && (
          <header className="h-14 border-b bg-background/80 backdrop-blur-sm flex items-center justify-between px-6 shrink-0 z-10 transition-all duration-300">
            <div className="flex items-center gap-2 font-semibold">
               {!config.show_sidebar && (
                 <div className="w-6 h-6 rounded bg-primary/20 flex items-center justify-center text-primary mr-1">
                    {pluginId.charAt(0).toUpperCase()}
                 </div>
               )}
               <span className="truncate">{config.public_page?.label || pluginId}</span>
            </div>
            
            <div className="flex items-center gap-4">
               {status && (
                 <div className="hidden sm:block text-[11px] text-muted-foreground">
                    Usage: {status.usage_count} / {status.free_clicks || '∞'}
                 </div>
               )}
               <UserMenu />
            </div>
          </header>
        )}

        <main 
          className="flex-1 relative overflow-auto"
          onClickCapture={handleWrapperClick}
        >
          {resolvedIframeUrl ? (
            <iframe
              ref={iframeRef}
              src={resolvedIframeUrl}
              className="w-full h-full border-none bg-background"
              title={pluginId}
            />
          ) : (
            <div className="w-full h-full">
              {children}
            </div>
          )}

          {/* Paywall Modal */}
          {status && config?.stripe_price_id && (
            <PluginPaywall 
              pluginId={pluginId} 
              tenantId={explicitTenantId} 
              open={status.trial_limit_reached && !status.is_paid}
              onOpenChange={handleModalOpenChange}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function UnavailableMessage({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-screen gap-4 text-muted-foreground">
      <div className="text-4xl animate-bounce">🔒</div>
      <div className="text-lg font-medium">{message}</div>
    </div>
  );
}
