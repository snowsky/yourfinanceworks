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
  // Note: token is no longer stored in localStorage (httpOnly cookie); check user data only
  const checkAuth = () => {
    const user = localStorage.getItem('user');

    if (!user) {
      setIsAuthenticated(false);
      setIsLoading(false);
      navigate('/login', { replace: true });
      return;
    }

    try {
      // Validate that user data is valid JSON
      JSON.parse(user);
      setIsAuthenticated(true);
      setIsLoading(false);
    } catch (error) {
      // Invalid user data, clear and redirect
      localStorage.removeItem('user');
      setIsAuthenticated(false);
      setIsLoading(false);
      navigate('/login', { replace: true });
    }
  };

  // Re-check auth on mount only
  useEffect(() => {
    checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Listen for storage events (cross-tab logout/login)
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
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
    return null; // Don't show loading state, just render nothing
  }

  // Don't render if not authenticated
  if (!isAuthenticated) {
    return null; // Don't render, just redirect silently
  }

  return <>{children}</>;
} 