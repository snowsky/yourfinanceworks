import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      const user = localStorage.getItem('user');

      console.log('ProtectedRoute: Checking authentication', { token: !!token, user: !!user });

      if (!token || !user) {
        console.log('ProtectedRoute: No token or user found, redirecting to login');
        setIsAuthenticated(false);
        setIsLoading(false);
        navigate('/login', { replace: true });
        return;
      }

      try {
        // Validate that user data is valid JSON
        JSON.parse(user);
        console.log('ProtectedRoute: Authentication valid');
        setIsAuthenticated(true);
        setIsLoading(false);
      } catch (error) {
        console.log('ProtectedRoute: Invalid user data, clearing and redirecting');
        // Invalid user data, clear and redirect
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setIsAuthenticated(false);
        setIsLoading(false);
        navigate('/login', { replace: true });
      }
    };

    checkAuth();
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