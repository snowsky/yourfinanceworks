import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Building2, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { authApi, API_BASE_URL } from '@/lib/api';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const Signup: React.FC = () => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    confirmPassword: '',
    organization_name: '',
    requested_role: 'user',
    message: ''
  });
  const [signupMode, setSignupMode] = useState<'create' | 'join'>('create');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [organizationNameStatus, setOrganizationNameStatus] = useState<{
    checking: boolean;
    available: boolean | null;
    message: string;
  }>({
    checking: false,
    available: null,
    message: ''
  });
  const [emailStatus, setEmailStatus] = useState<{
    checking: boolean;
    available: boolean | null;
    message: string;
  }>({
    checking: false,
    available: null,
    message: ''
  });
  const [ssoStatus, setSsoStatus] = useState<{ google: boolean; microsoft: boolean; has_sso: boolean } | null>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const navigate = useNavigate();

  // Debounced organization name availability check
  const checkOrganizationNameAvailability = useCallback(async (name: string) => {
    if (!name) {
      setOrganizationNameStatus({
        checking: false,
        available: null,
        message: ''
      });
      return;
    }

    if (name.length < 2) {
      setOrganizationNameStatus({
        checking: false,
        available: false,
        message: t('auth.signup.availability.org_min_length')
      });
      return;
    }

    setOrganizationNameStatus({
      checking: true,
      available: null,
      message: t('auth.signup.availability.checking')
    });

    try {
      if (signupMode === 'create') {
        // Check if name is available for new organization
        const result = await authApi.checkOrganizationNameAvailability(name);
        setOrganizationNameStatus({
          checking: false,
          available: result.available,
          message: result.available
            ? t('auth.signup.availability.org_available')
            : t('auth.signup.availability.org_taken')
        });
      } else {
        // Check if organization exists to join
        const result = await authApi.lookupOrganization(name);
        setOrganizationNameStatus({
          checking: false,
          available: result.exists,
          message: result.message
        });
      }
    } catch (error) {
      setOrganizationNameStatus({
        checking: false,
        available: null,
        message: t('auth.signup.availability.error_checking')
      });
    }
  }, [signupMode]);

  // Debounced email availability check
  const checkEmailAvailability = useCallback(async (email: string) => {
    if (!email) {
      setEmailStatus({
        checking: false,
        available: null,
        message: ''
      });
      return;
    }

    // Basic email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setEmailStatus({
        checking: false,
        available: false,
        message: t('auth.signup.availability.valid_email')
      });
      return;
    }

    setEmailStatus({
      checking: true,
      available: null,
      message: t('auth.signup.availability.checking')
    });

    try {
      const result = await authApi.checkEmailAvailability(email);
      setEmailStatus({
        checking: false,
        available: result.available,
        message: result.available
          ? t('auth.signup.availability.email_available')
          : t('auth.signup.availability.email_taken')
      });
    } catch (error) {
      setEmailStatus({
        checking: false,
        available: null,
        message: t('auth.signup.availability.error_checking')
      });
    }
  }, []);

  // Debounce the organization name check
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (formData.organization_name) {
        checkOrganizationNameAvailability(formData.organization_name);
      }
    }, 500); // 500ms delay

    return () => clearTimeout(timeoutId);
  }, [formData.organization_name, checkOrganizationNameAvailability]);

  // Debounce the email availability check
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (formData.email) {
        checkEmailAvailability(formData.email);
      }
    }, 500); // 500ms delay

    return () => clearTimeout(timeoutId);
  }, [formData.email, checkEmailAvailability]);

  // Fetch SSO status on component mount
  useEffect(() => {
    const fetchSSOStatus = async () => {
      try {
        const status = await authApi.getSSOStatus();
        setSsoStatus(status);
      } catch (error) {
        console.error('Failed to fetch SSO status:', error);
        // Default to showing SSO if API fails
        setSsoStatus({ google: true, microsoft: true, has_sso: true });
      }
    };

    fetchSSOStatus();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleAzureLogin = () => {
    const next = encodeURIComponent('/dashboard');
    const url = `${API_BASE_URL}/auth/azure/login?next=${next}`;
    window.location.href = url;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      setError(t('auth.signup.validation.passwords_not_match'));
      setLoading(false);
      return;
    }

    // Validate password strength
    if (formData.password.length < 6) {
      setError(t('auth.signup.validation.password_min_length'));
      setLoading(false);
      return;
    }

    // Validate email availability
    if (emailStatus.available === false) {
      setError(t('auth.signup.validation.email_not_available'));
      setLoading(false);
      return;
    }

    // If we're still checking email availability, wait for it to complete
    if (emailStatus.checking) {
      setError(t('auth.signup.validation.waiting_email_check'));
      setLoading(false);
      return;
    }

    // Validate organization name availability
    if (organizationNameStatus.available === false) {
      setError(t('auth.signup.validation.org_not_available'));
      setLoading(false);
      return;
    }

    // If we're still checking availability, wait for it to complete
    if (organizationNameStatus.checking) {
      setError(t('auth.signup.validation.waiting_org_check'));
      setLoading(false);
      return;
    }

    try {
      if (signupMode === 'create') {
        // Regular signup - create new organization
        const data = await authApi.register(formData);
        // Clear any previous tenant selection
        localStorage.removeItem('selected_tenant_id');
        // Store token and user info
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        // Dispatch custom event to notify FeatureContext
        window.dispatchEvent(new Event('auth-changed'));
        navigate('/dashboard');
      } else {
        // Join existing organization - submit join request
        const result = await authApi.submitJoinRequest({
          email: formData.email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          password: formData.password,
          organization_name: formData.organization_name,
          requested_role: formData.requested_role,
          message: formData.message
        });

        if (result.success) {
          // Show success modal and redirect to login after closing
          setSuccessMessage(result.message);
          setShowSuccessModal(true);
        } else {
          setError(result.message);
        }
      }
    } catch (err: any) {
      setError(err.message || t('auth.signup.validation.registration_failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {t('auth.signup.title')}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            {t('auth.signup.subtitle')}
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md">
              {error}
            </div>
          )}

          <div className="space-y-4">
            {/* Mode Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                How would you like to get started?
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setSignupMode('create');
                    // Reset organization status when switching modes
                    setOrganizationNameStatus({ checking: false, available: null, message: '' });
                    if (formData.organization_name) {
                      checkOrganizationNameAvailability(formData.organization_name);
                    }
                  }}
                  className={`p-3 text-left border rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 ${signupMode === 'create'
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-gray-300 bg-white text-gray-900 hover:bg-gray-50'
                    }`}
                >
                  <div className="font-medium">Create new organization</div>
                  <div className="text-xs text-gray-500">Start fresh with your own organization</div>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSignupMode('join');
                    // Reset organization status when switching modes
                    setOrganizationNameStatus({ checking: false, available: null, message: '' });
                    if (formData.organization_name) {
                      checkOrganizationNameAvailability(formData.organization_name);
                    }
                  }}
                  className={`p-3 text-left border rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 ${signupMode === 'join'
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-gray-300 bg-white text-gray-900 hover:bg-gray-50'
                    }`}
                >
                  <div className="font-medium">Join existing organization</div>
                  <div className="text-xs text-gray-500">Request to join an organization</div>
                </button>
              </div>
            </div>

            {/* Organization Name */}
            <div>
              <label htmlFor="organization_name" className="block text-sm font-medium text-gray-700">
                {signupMode === 'create' ? 'Organization Name' : 'Organization to Join'}
              </label>
              <div className="mt-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Building2 className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  id="organization_name"
                  name="organization_name"
                  type="text"
                  required
                  className={`appearance-none relative block w-full pl-10 pr-12 py-2 border placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm ${organizationNameStatus.available === false
                    ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                    : organizationNameStatus.available === true
                      ? 'border-green-300 focus:ring-green-500 focus:border-green-500'
                      : 'border-gray-300'
                    }`}
                  placeholder={signupMode === 'create' ? 'Enter your organization name' : 'Enter organization name to join'}
                  value={formData.organization_name}
                  onChange={handleChange}
                />
                {/* Availability indicator */}
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                  {organizationNameStatus.checking && (
                    <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
                  )}
                  {organizationNameStatus.available === true && (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  )}
                  {organizationNameStatus.available === false && (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                </div>
              </div>
              {/* Status message */}
              {organizationNameStatus.message && (
                <div className={`mt-2 p-2 rounded-md text-sm ${organizationNameStatus.available === true
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : organizationNameStatus.available === false
                    ? 'bg-red-50 border border-red-200 text-red-700'
                    : 'bg-gray-50 border border-gray-200 text-gray-700'
                  }`}>
                  {organizationNameStatus.message}
                  {organizationNameStatus.available === false && organizationNameStatus.message.includes('already taken') && (
                    <div className="mt-2 pt-2 border-t border-red-200">
                      <p className="text-xs text-red-600">
                        {t('auth.signup.tips.org_taken_tip')}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* First Name */}
            <div>
              <label htmlFor="first_name" className="block text-sm font-medium text-gray-700">
                {t('auth.signup.first_name')}
              </label>
              <input
                id="first_name"
                name="first_name"
                type="text"
                required
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder={t('auth.signup.first_name_placeholder')}
                value={formData.first_name}
                onChange={handleChange}
              />
            </div>

            {/* Last Name */}
            <div>
              <label htmlFor="last_name" className="block text-sm font-medium text-gray-700">
                {t('auth.signup.last_name')}
              </label>
              <input
                id="last_name"
                name="last_name"
                type="text"
                required
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder={t('auth.signup.last_name_placeholder')}
                value={formData.last_name}
                onChange={handleChange}
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                {t('auth.signup.email_address')}
              </label>
              <div className="mt-1 relative">
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  className={`appearance-none relative block w-full px-3 py-2 pr-12 border placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm ${emailStatus.available === false
                    ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                    : emailStatus.available === true
                      ? 'border-green-300 focus:ring-green-500 focus:border-green-500'
                      : 'border-gray-300'
                    }`}
                  placeholder={t('auth.signup.email_placeholder')}
                  value={formData.email}
                  onChange={handleChange}
                />
                {/* Availability indicator */}
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                  {emailStatus.checking && (
                    <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
                  )}
                  {emailStatus.available === true && (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  )}
                  {emailStatus.available === false && (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                </div>
              </div>
              {/* Status message */}
              {emailStatus.message && (
                <div className={`mt-2 p-2 rounded-md text-sm ${emailStatus.available === true
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : emailStatus.available === false
                    ? 'bg-red-50 border border-red-200 text-red-700'
                    : 'bg-gray-50 border border-gray-200 text-gray-700'
                  }`}>
                  {emailStatus.message}
                  {emailStatus.available === false && emailStatus.message.includes('already registered') && (
                    <div className="mt-2 pt-2 border-t border-red-200">
                      <p className="text-xs text-red-600">
                        {t('auth.signup.tips.email_taken_tip')}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                {t('auth.signup.password')}
              </label>
              <div className="mt-1 relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  className="appearance-none relative block w-full px-3 py-2 pr-10 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder={t('auth.signup.password_placeholder')}
                  value={formData.password}
                  onChange={handleChange}
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

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                {t('auth.signup.confirm_password')}
              </label>
              <div className="mt-1 relative">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  className="appearance-none relative block w-full px-3 py-2 pr-10 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                  placeholder={t('auth.signup.confirm_password_placeholder')}
                  value={formData.confirmPassword}
                  onChange={handleChange}
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

            {/* Additional fields for join mode */}
            {signupMode === 'join' && (
              <>
                {/* Role Selection */}
                <div>
                  <label htmlFor="requested_role" className="block text-sm font-medium text-gray-700">
                    Requested Role
                  </label>
                  <select
                    id="requested_role"
                    name="requested_role"
                    value={formData.requested_role}
                    onChange={(e) => setFormData({ ...formData, requested_role: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>

                {/* Optional Message */}
                <div>
                  <label htmlFor="message" className="block text-sm font-medium text-gray-700">
                    Message to Admin (Optional)
                  </label>
                  <textarea
                    id="message"
                    name="message"
                    rows={3}
                    value={formData.message}
                    onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                    placeholder="Tell the admin why you want to join this organization..."
                  />
                </div>
              </>
            )}
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ?
                (signupMode === 'create' ? 'Creating Account...' : 'Submitting Request...') :
                (signupMode === 'create' ? 'Create Account' : 'Request to Join')
              }
            </button>
          </div>

          <div className="text-center">
            <span className="text-sm text-gray-600">
              {t('auth.signup.already_have_account')}{' '}
              <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
                {t('auth.signup.sign_in')}
              </Link>
            </span>
          </div>

          {ssoStatus?.has_sso && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-gray-50 text-gray-500">{t('auth.signup.or_continue_with')}</span>
                </div>
              </div>

              {ssoStatus.google && (
                <div className="mt-6">
                  <button
                    type="button"
                    className="w-full inline-flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                    onClick={() => {
                      const next = encodeURIComponent('/dashboard');
                      const url = `${API_BASE_URL}/auth/google/login?next=${next}`;
                      window.location.href = url;
                    }}
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    <span className="ml-2">{t('auth.signup.sign_up_with_google')}</span>
                  </button>
                </div>
              )}

              {ssoStatus.microsoft && (
                <div className="mt-3">
                  <button
                    type="button"
                    className="w-full inline-flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                    onClick={handleAzureLogin}
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path
                        d="M12.5 1.5L5.5 3.5v7c0 5.5 3.8 10.7 7 12 3.2-1.3 7-6.5 7-12v-7l-7-2z"
                        fill="#00BCF2"
                      />
                      <path
                        d="M12.5 1.5v21c3.2-1.3 7-6.5 7-12v-7l-7-2z"
                        fill="#0078D4"
                      />
                    </svg>
                    <span className="ml-2">{t('auth.signup.sign_up_with_microsoft')}</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </form>

        {/* Success Modal */}
        <Dialog open={showSuccessModal} onOpenChange={(open) => {
          setShowSuccessModal(open);
          if (!open) {
            navigate('/login');
          }
        }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Join Request Submitted</DialogTitle>
              <DialogDescription>
                {successMessage}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button onClick={() => {
                setShowSuccessModal(false);
                navigate('/login');
              }}>
                OK
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default Signup; 