import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';

interface RoleProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles: string[];
  redirectTo?: string;
}

export function RoleProtectedRoute({ 
  children, 
  allowedRoles, 
  redirectTo = '/' 
}: RoleProtectedRouteProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Role check logic
  const checkRole = () => {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');

    console.log('RoleProtectedRoute: Checking role authorization', { path: location.pathname });

    if (!token || !user) {
      console.log('RoleProtectedRoute: No token or user found, redirecting to login');
      setIsAuthorized(false);
      setIsLoading(false);
      navigate('/login', { replace: true });
      return;
    }

    try {
      const userData = JSON.parse(user);
      const userRole = userData?.role || 'user';
      
      console.log('RoleProtectedRoute: User role:', userRole, 'Allowed roles:', allowedRoles);
      
      if (allowedRoles.includes(userRole)) {
        console.log('RoleProtectedRoute: Role authorized');
        setIsAuthorized(true);
        setIsLoading(false);
      } else {
        console.log('RoleProtectedRoute: Role not authorized, redirecting');
        setIsAuthorized(false);
        setIsLoading(false);
        toast.error('You do not have permission to access this page');
        navigate(redirectTo, { replace: true });
      }
    } catch (error) {
      console.log('RoleProtectedRoute: Invalid user data, clearing and redirecting');
      // Invalid user data, clear and redirect
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      setIsAuthorized(false);
      setIsLoading(false);
      navigate('/login', { replace: true });
    }
  };

  // Re-check role on mount and on every route change
  useEffect(() => {
    checkRole();
    // eslint-disable-next-line
  }, [navigate, location]);

  // Listen for localStorage changes (for immediate detection when user role changes)
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'user' || e.key === 'token') {
        checkRole();
      }
    };

    window.addEventListener('storage', handleStorage);

    return () => {
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p>Checking permissions...</p>
        </div>
      </div>
    );
  }

  if (!isAuthorized) {
    return null; // Component will redirect, so don't render anything
  }

  return <>{children}</>;
} 