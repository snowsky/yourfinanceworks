import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-i18next'
import { apiRequest } from '@/lib/api/_base';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useNavigate as routerUseNavigate, useLocation as routerUseLocation } from 'react-router-dom';

interface PluginAuthProps {
  pluginId: string;
  tenantId?: string;
  onAuthenticated: () => void;
}

export function PluginAuth({ pluginId, tenantId, onAuthenticated }: PluginAuthProps) {
  const { t } = useTranslation();
  const navigate = routerUseNavigate();
  const location = routerUseLocation();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenantId) {
       toast.error("Tenant ID is required for authentication");
       return;
    }
    setLoading(true);
    try {
      const endpoint = isLogin ? 'login' : 'signup';
      const data = await apiRequest<{access_token: string, user: any}>(`/plugins/${pluginId}/public-auth/${endpoint}`, {
        method: 'POST',
        body: JSON.stringify({ email, password, tenant_id: parseInt(tenantId, 10) })
      });
      
      const tokenKey = `plugin_token_${pluginId}`;
      localStorage.setItem(tokenKey, JSON.stringify(data));
      onAuthenticated();
    } catch (err: any) {
      toast.error(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSSO = (provider: 'google' | 'azure') => {
    if (!tenantId) {
      toast.error("Tenant ID is required for SSO");
      return;
    }
    // Record the current pathname so we can redirect back here after OAuth callback
    const returnUrl = encodeURIComponent(location.pathname + location.search);
    window.location.href = `/api/v1/plugins/${pluginId}/public-auth/${provider}/login?tenant_id=${tenantId}&next=${returnUrl}`;
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-muted/30">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
             {isLogin ? t('plugins.auth.login', 'Sign In') : t('plugins.auth.signup', 'Sign Up')}
          </CardTitle>
          <CardDescription>
             {t('plugins.auth.instruction', 'Access this plugin.')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" required value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" required value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {isLogin ? 'Sign In' : 'Sign Up'}
            </Button>
            
            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-2">
               <Button type="button" variant="outline" onClick={() => handleSSO('google')}>Google</Button>
               <Button type="button" variant="outline" onClick={() => handleSSO('azure')}>Microsoft</Button>
            </div>
            
            <div className="mt-4 text-center text-sm">
               <button type="button" className="text-primary hover:underline" onClick={() => setIsLogin(!isLogin)}>
                  {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
               </button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
