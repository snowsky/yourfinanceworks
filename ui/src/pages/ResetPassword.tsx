import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, CheckCircle } from 'lucide-react';
import { AuthLayout, AuthHeading, AuthErrorBanner } from '@/components/auth/AuthLayout';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { authApi, getErrorMessage } from '@/lib/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

const ResetPassword: React.FC = () => {
  const { t } = useTranslation();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [passwordRequirements, setPasswordRequirements] = useState<any>(null);
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const urlToken = searchParams.get('token');
    if (urlToken) {
      setToken(urlToken);
    } else {
      setError(t('resetPassword.noToken'));
    }

    // Fetch password requirements
    const fetchPasswordRequirements = async () => {
      try {
        const requirements = await authApi.getPasswordRequirements();
        setPasswordRequirements(requirements);
      } catch (error) {
        console.error('Failed to fetch password requirements:', error);
        // Fallback to default requirements
        setPasswordRequirements({
          min_length: 8,
          complexity: {
            require_uppercase: true,
            require_lowercase: true,
            require_numbers: true,
            require_special_chars: true,
            special_chars: "!@#$%^&*()_+-=[]{}|;:,.<>?"
          }
        });
      }
    };

    fetchPasswordRequirements();
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
    if (!passwordRequirements) {
      setError(t('resetPassword.requirementsNotLoaded'));
      setIsLoading(false);
      return;
    }

    const passwordValidation = {
      hasUppercase: /[A-Z]/.test(password),
      hasLowercase: /[a-z]/.test(password),
      hasNumbers: /\d/.test(password),
      hasSpecialChars: new RegExp(`[${passwordRequirements.complexity.special_chars.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}]`).test(password)
    };

    const passwordErrors = [];
    if (password.length < passwordRequirements.min_length) {
      passwordErrors.push(t('resetPassword.passwordMinLength', { min_length: passwordRequirements.min_length }));
    }
    if (passwordRequirements.complexity.require_uppercase && !passwordValidation.hasUppercase) {
      passwordErrors.push(t('resetPassword.requireUppercase'));
    }
    if (passwordRequirements.complexity.require_lowercase && !passwordValidation.hasLowercase) {
      passwordErrors.push(t('resetPassword.requireLowercase'));
    }
    if (passwordRequirements.complexity.require_numbers && !passwordValidation.hasNumbers) {
      passwordErrors.push(t('resetPassword.requireNumber'));
    }
    if (passwordRequirements.complexity.require_special_chars && !passwordValidation.hasSpecialChars) {
      passwordErrors.push(t('resetPassword.requireSpecialChar'));
    }

    if (passwordErrors.length > 0) {
      setError(passwordErrors.join('. '));
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
      <AuthLayout>
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
          <CheckCircle className="h-6 w-6 text-success" aria-hidden="true" />
        </div>
        <AuthHeading
          title={t('resetPassword.successTitle')}
          description={t('resetPassword.successDescription')}
        />
        <ProfessionalButton asChild variant="gradient" size="xl" className="w-full">
          <Link to="/login">{t('resetPassword.goToLogin')}</Link>
        </ProfessionalButton>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthHeading title={t('resetPassword.title')} description={t('resetPassword.description')} />
      <AuthErrorBanner message={error} />

      <form onSubmit={handleSubmit} className="space-y-4">
        <ProfessionalInput
          id="password"
          name="password"
          type="password"
          label={t('resetPassword.newPasswordLabel')}
          placeholder={t('resetPassword.newPasswordPlaceholder')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          required
          inputSize="lg"
        />

        <ProfessionalInput
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          label={t('resetPassword.confirmPasswordLabel')}
          placeholder={t('resetPassword.confirmPasswordPlaceholder')}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          autoComplete="new-password"
          required
          inputSize="lg"
        />

        <ProfessionalButton
          type="submit"
          variant="gradient"
          size="xl"
          className="w-full mt-2"
          loading={isLoading}
          disabled={!token}
        >
          {isLoading ? t('resetPassword.resetting') : t('resetPassword.resetPasswordButton')}
        </ProfessionalButton>
      </form>

      <Link
        to="/login"
        className="mt-6 flex items-center justify-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t('resetPassword.backToLogin')}
      </Link>
    </AuthLayout>
  );
};

export default ResetPassword;
