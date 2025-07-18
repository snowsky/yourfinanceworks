import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Eye, EyeOff, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';
import { authApi } from '@/lib/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { getErrorMessage } from '@/lib/api';

const ResetPassword: React.FC = () => {
  const { t } = useTranslation();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken) {
      setToken(urlToken);
    } else {
      setError(t('resetPassword.noToken'));
    }
  }, [searchParams, t]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    // Validate passwords match
    if (password !== confirmPassword) {
      setError(t('resetPassword.passwordsNotMatch'));
      setIsLoading(false);
      return;
    }

    // Validate password strength
    if (password.length < 6) {
      setError(t('resetPassword.passwordMinLength'));
      setIsLoading(false);
      return;
    }

    if (!token) {
      setError(t('resetPassword.noToken'));
      setIsLoading(false);
      return;
    }

    try {
      const response = await authApi.resetPassword(token, password);
      
      if (response.success) {
        setIsSuccess(true);
        toast.success(t('resetPassword.toastSuccess'));
      } else {
        setError(response.message || t('resetPassword.toastError'));
      }
    } catch (error: any) {
      const errorMessage = getErrorMessage(error, t);
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <Card>
            <CardHeader className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <CardTitle className="mt-4 text-2xl font-bold text-gray-900">
                {t('resetPassword.successTitle')}
              </CardTitle>
              <CardDescription className="mt-2">
                {t('resetPassword.successDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Button
                onClick={() => navigate('/login')}
                className="w-full"
              >
                {t('resetPassword.goToLogin')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <Card>
          <CardHeader className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-blue-100">
              <AlertCircle className="h-6 w-6 text-blue-600" />
            </div>
            <CardTitle className="mt-4 text-2xl font-bold text-gray-900">
              {t('resetPassword.title')}
            </CardTitle>
            <CardDescription className="mt-2">
              {t('resetPassword.description')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md">
                  {error}
                </div>
              )}
              
              <div>
                <Label htmlFor="password" className="block text-sm font-medium text-gray-700">
                  {t('resetPassword.newPasswordLabel')}
                </Label>
                <div className="mt-1 relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    placeholder={t('resetPassword.newPasswordPlaceholder')}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5 text-gray-400" />
                    ) : (
                      <Eye className="h-5 w-5 text-gray-400" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <Label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                  {t('resetPassword.confirmPasswordLabel')}
                </Label>
                <div className="mt-1 relative">
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    placeholder={t('resetPassword.confirmPasswordPlaceholder')}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-5 w-5 text-gray-400" />
                    ) : (
                      <Eye className="h-5 w-5 text-gray-400" />
                    )}
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                <Button
                  type="submit"
                  disabled={isLoading || !token}
                  className="w-full"
                >
                  {isLoading ? t('resetPassword.resetting') : t('resetPassword.resetPasswordButton')}
                </Button>
                
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => navigate('/login')}
                  className="w-full"
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  {t('resetPassword.backToLogin')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
        
        <div className="text-center">
          <p className="text-sm text-gray-600">
            {t('resetPassword.rememberPassword')}{' '}
            <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
              {t('resetPassword.signIn')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword; 