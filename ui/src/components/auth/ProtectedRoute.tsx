import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Auth check logic extracted for reuse
  const checkAuth = () => {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');

    console.log('ProtectedRoute: Checking authentication', { 
      token: !!token, 
      user: !!user,
      tokenLength: token?.length,
      userLength: user?.length,
      path: location.pathname
    });

    if (!token || !user) {
      console.log('ProtectedRoute: No token or user found, redirecting to login');
      setIsAuthenticated(false);
      setIsLoading(false);
      navigate('/login', { replace: true });
      return;
    }

    try {
      // Validate that user data is valid JSON
      const userData = JSON.parse(user);
      console.log('ProtectedRoute: Authentication valid', { 
        userData,
        role: userData?.role,
        email: userData?.email 
      });
      setIsAuthenticated(true);
      setIsLoading(false);
    } catch (error) {
      console.log('ProtectedRoute: Invalid user data, clearing and redirecting', { error });
      // Invalid user data, clear and redirect
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      setIsAuthenticated(false);
      setIsLoading(false);
      navigate('/login', { replace: true });
    }
  };

  // Re-check auth on mount and on every route change
  useEffect(() => {
    checkAuth();
    // eslint-disable-next-line
  }, [navigate, location]);

  // Listen for storage events (cross-tab logout/login)
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'token' && !localStorage.getItem('token')) {
        console.log('ProtectedRoute: Detected token removal via storage event, redirecting to login');
        setIsAuthenticated(false);
        setIsLoading(false);
        navigate('/login', { replace: true });
      }
      if (e.key === 'user' && !localStorage.getItem('user')) {
        console.log('ProtectedRoute: Detected user removal via storage event, redirecting to login');
        setIsAuthenticated(false);
        setIsLoading(false);
        navigate('/login', { replace: true });
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [navigate]);

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
} 