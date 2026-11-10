import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle } from 'lucide-react';
import { AuthLayout, AuthHeading, AuthErrorBanner } from '@/components/auth/AuthLayout';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { authApi, getErrorMessage } from '@/lib/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

const BackToLogin = ({ label }: { label: string }) => (
  <Link
    to="/login"
    className="mt-6 flex items-center justify-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
  >
    <ArrowLeft className="h-4 w-4" aria-hidden="true" />
    {label}
  </Link>
);

const ForgotPassword: React.FC = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.requestPasswordReset(email);

      if (response.success) {
        setIsSubmitted(true);
        toast.success(t('forgotPassword.toastSuccess'));
      } else {
        setError(t('forgotPassword.toastError'));
      }
    } catch (error: any) {
      const errorMessage = getErrorMessage(error, t);
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <AuthLayout>
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
          <CheckCircle className="h-6 w-6 text-success" aria-hidden="true" />
        </div>
        <AuthHeading
          title={t('forgotPassword.checkEmailTitle')}
          description={t('forgotPassword.checkEmailDescription')}
        />
        <p className="text-sm text-muted-foreground">{t('forgotPassword.checkSpam')}</p>

        <ProfessionalButton
          type="button"
          variant="outline"
          size="xl"
          className="w-full mt-8"
          onClick={() => {
            setIsSubmitted(false);
            setEmail('');
          }}
        >
          {t('forgotPassword.sendAnother')}
        </ProfessionalButton>
        <BackToLogin label={t('forgotPassword.backToLogin')} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthHeading title={t('forgotPassword.title')} description={t('forgotPassword.description')} />
      <AuthErrorBanner message={error} />

      <form onSubmit={handleSubmit} className="space-y-4">
        <ProfessionalInput
          id="email"
          name="email"
          type="email"
          label={t('forgotPassword.emailLabel')}
          placeholder={t('forgotPassword.emailPlaceholder')}
          value={email}
          onChange={(e) => { setEmail(e.target.value); setError(null); }}
          autoComplete="email"
          required
          inputSize="lg"
        />

        <ProfessionalButton
          type="submit"
          variant="gradient"
          size="xl"
          className="w-full mt-2"
          loading={isLoading}
        >
          {isLoading ? t('forgotPassword.sending') : t('forgotPassword.sendResetLink')}
        </ProfessionalButton>
      </form>

      <BackToLogin label={t('forgotPassword.backToLogin')} />

      <p className="mt-8 text-center text-sm text-muted-foreground">
        {t('forgotPassword.noAccount')}{' '}
        <Link to="/signup" className="text-primary hover:text-primary/80 font-semibold transition-colors">
          {t('forgotPassword.signUp')}
        </Link>
      </p>
    </AuthLayout>
  );
};

export default ForgotPassword;
