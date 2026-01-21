import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

interface TenantProtectedRouteProps {
  children: React.ReactNode;
  requirePrimaryTenant?: boolean;
  requireSuperUser?: boolean;
  redirectTo?: string;
}

export function TenantProtectedRoute({ 
  children, 
  requirePrimaryTenant = false,
  requireSuperUser = false,
  redirectTo = '/' 
}: TenantProtectedRouteProps) {
  const navigate = useNavigate();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAccess = () => {
      try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        const selectedTenantId = localStorage.getItem('selected_tenant_id');
        const userTenantId = user?.tenant_id?.toString();
        const currentTenantId = selectedTenantId || userTenantId;

        console.log('TenantProtectedRoute check:', {
          requireSuperUser,
          requirePrimaryTenant,
          userIsSuperUser: user?.is_superuser,
          userTenantId,
          selectedTenantId,
          currentTenantId
        });

        if (requireSuperUser && !user?.is_superuser) {
          console.log('User is not super admin, redirecting');
          toast.error('Super admin access required');
          navigate(redirectTo, { replace: true });
          return;
        }

        // For primary tenant check, only redirect if selected_tenant_id is explicitly set to a different tenant
        if (requirePrimaryTenant && selectedTenantId && selectedTenantId !== userTenantId) {
          console.log('User is not in primary tenant, redirecting');
          toast.error('Access restricted to home organization');
          navigate(redirectTo, { replace: true });
          return;
        }

        console.log('TenantProtectedRoute: Access granted');
        setIsAuthorized(true);
      } catch (error) {
        console.error('TenantProtectedRoute error:', error);
        setIsAuthorized(false);
      }
    };

    checkAccess();
  }, [requirePrimaryTenant, requireSuperUser, navigate, redirectTo]);

  if (isAuthorized === null) {
    return null; // Don't show loading state, just render nothing until check completes
  }

  if (!isAuthorized) {
    return null; // Don't render if not authorized
  }

  return <>{children}</>;
}