import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { MessageCircle, Send, User, Bot, Maximize2, Minimize2, TrendingUp, ExternalLink, Sparkles, X, Zap, CheckCircle, AlertCircle, Clock, Activity, Users, DollarSign, Calendar, BarChart3, Lightbulb, Target, Star, Loader } from 'lucide-react';
import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import PaymentCharts from './PaymentCharts';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/components/ui/use-toast';

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string | React.ReactNode;
}

interface ApiCall {
  id: string;
  method: string;
  url: string;
  status: string;
  duration: number;
  timestamp: string;
  error?: string;
}

// Styled AI Response Component
const StyledAIResponse = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 p-4 rounded-xl border border-indigo-200 shadow-lg">
    <div className="flex items-start gap-3">
      <div className="bg-gradient-to-br from-indigo-500 to-purple-500 rounded-full p-2 shadow-md">
        <Sparkles className="h-4 w-4 text-white" />
      </div>
      <div className="flex-1">
        <div className="text-gray-800 leading-relaxed">
          {children}
        </div>
      </div>
    </div>
  </div>
);

// Enhanced AI Response with different styles based on content
const EnhancedAIResponse = ({ text }: { text: string }) => {
  // Check if the response contains specific patterns to apply different styling
  const lowerText = text.toLowerCase();
  
  if (lowerText.includes('error') || lowerText.includes('sorry') || lowerText.includes('failed')) {
    return (
      <div className="bg-gradient-to-br from-red-50 to-pink-50 p-4 rounded-xl border border-red-200 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="bg-gradient-to-br from-red-500 to-pink-500 rounded-full p-2 shadow-md">
            <MessageCircle className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1">
            <div className="text-red-800 leading-relaxed font-medium">
              {text}
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  if (lowerText.includes('success') || lowerText.includes('great') || lowerText.includes('excellent')) {
    return (
      <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-4 rounded-xl border border-green-200 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="bg-gradient-to-br from-green-500 to-emerald-500 rounded-full p-2 shadow-md">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1">
            <div className="text-green-800 leading-relaxed font-medium">
              {text}
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  if (lowerText.includes('configuration') || lowerText.includes('settings')) {
    return (
      <div className="bg-gradient-to-br from-blue-50 to-cyan-50 p-4 rounded-xl border border-blue-200 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full p-2 shadow-md">
            <MessageCircle className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1">
            <div className="text-blue-800 leading-relaxed">
              {text}
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  // Default styled response
  return <StyledAIResponse>{text}</StyledAIResponse>;
};

const AIAssistant = React.forwardRef<HTMLDivElement>((props, ref) => {
  // Check authentication and user role first
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [isAdminUser, setIsAdminUser] = useState(false);
  const [authInitialized, setAuthInitialized] = useState(false);

  // Check authentication and user role
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      const userStr = localStorage.getItem('user');
      const authStatus = !!(token && userStr);
      
      let currentUser = null;
      let adminStatus = false;
      
      if (authStatus && userStr) {
        try {
          currentUser = JSON.parse(userStr);
          adminStatus = currentUser?.role === 'admin' || currentUser?.is_superuser === true;
        } catch (e) {
          console.error('Error parsing user data:', e);
          // If user data is corrupted, consider user as logged out
          setIsAuthenticated(false);
          setUser(null);
          setIsAdminUser(false);
          setAuthInitialized(true);
          return;
        }
      }
      
      setIsAuthenticated(authStatus);
      setUser(currentUser);
      setIsAdminUser(adminStatus);
      setAuthInitialized(true);
      
      // console.log('AI Assistant: Auth status update', { 
      //   hasToken: !!token, 
      //   hasUser: !!currentUser, 
      //   authStatus, 
      //   adminStatus,
      //   shouldShow: authStatus && adminStatus 
      // });
    };
    
    checkAuth();
    
    // Check authentication on localStorage changes
    const handleStorageChange = (e: StorageEvent) => {
      // If token is removed, immediately hide AI assistant
      if (e.key === 'token' && !e.newValue) {
        // console.log('AI Assistant: Token removed, hiding assistant');
        setIsAuthenticated(false);
        setUser(null);
        setIsAdminUser(false);
        return;
      }
      // If user data is removed, hide assistant
      if (e.key === 'user' && !e.newValue) {
        // console.log('AI Assistant: User data removed, hiding assistant');
        setIsAuthenticated(false);
        setUser(null);
        setIsAdminUser(false);
        return;
      }
      // If token or user is added (login), immediately check auth
      if ((e.key === 'token' && e.newValue) || (e.key === 'user' && e.newValue)) {
        // console.log('AI Assistant: Login detected, checking auth');
        setTimeout(checkAuth, 100); // Small delay to ensure both token and user are set
        return;
      }
      checkAuth();
    };
    
    // Listen for storage events (from other tabs)
    window.addEventListener('storage', handleStorageChange);
    
    // Listen for logout events
    const handleLogout = () => {
      // console.log('AI Assistant: Logout event received, hiding assistant');
      setIsAuthenticated(false);
      setUser(null);
      setIsAdminUser(false);
    };
    
    window.addEventListener('user-logout', handleLogout);
    
    // Check auth every 1 second for immediate logout detection
    const authInterval = setInterval(() => {
      const token = localStorage.getItem('token');
      const userStr = localStorage.getItem('user');
      
      // If either token or user data is missing, hide the assistant
      if (!token || !userStr) {
        if (isAuthenticated) { // Only log if state changes
          // console.log('AI Assistant: Auth check interval - hiding due to missing credentials');
          setIsAuthenticated(false);
          setUser(null);
          setIsAdminUser(false);
        }
      } else if (!isAuthenticated) {
        // If credentials exist but we think user is not authenticated, recheck
        // console.log('AI Assistant: Auth check interval - credentials found, rechecking auth');
        checkAuth();
      }
    }, 1000);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('user-logout', handleLogout);
      clearInterval(authInterval);
    };
  }, []); // Keep empty dependency array but remove stale closure issue

  // Don't render anything until auth is initialized
  if (!authInitialized) {
    return null;
  }

  // Return the appropriate component based on authentication state
  if (!isAuthenticated || !isAdminUser) {
    // console.log('AI Assistant: Not rendering - auth check failed', { 
    //   isAuthenticated, 
    //   isAdminUser,
    //   authInitialized,
    //   reason: !isAuthenticated ? 'not authenticated' : 'not admin user'
    // });
    return null;
  }

  // console.log('AI Assistant: Rendering for authenticated admin user');
  return <AuthenticatedAIAssistant user={user} ref={ref} />;
});

// Separate component for authenticated admin users
const AuthenticatedAIAssistant = React.forwardRef<HTMLDivElement, { user: any }>((props, ref) => {
  const { user } = props;
  const { t } = useTranslation();
  
  const [isOpen, setIsOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [messages, setMessages] = useState<Message[]>(
    [{ id: 1, sender: 'ai', text: <EnhancedAIResponse text={t('aiAssistant.welcomeMessage')} /> }]
  );
  const [input, setInput] = useState('');
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  // Auto-scroll to bottom when messages change
  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch user settings to check the enable_ai_assistant flag (only for admin users)
  const { data: settings, isLoading: settingsLoading, error: settingsError, refetch: refetchSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings/'),
    refetchInterval: (query) => {
      // Stop refetching if there's an authentication error
      if (query.state.error && 
          (query.state.error.message.includes('403') || 
           query.state.error.message.includes('Authentication failed'))) {
        // console.log('AI Assistant: Stopping refetch due to authentication error');
        return false;
      }
      // Only refetch if AI assistant is not explicitly disabled
      const currentSettings = query.state.data;
      return currentSettings && !(currentSettings as any)?.enable_ai_assistant ? false : 30000;
    },
    retry: (failureCount, error) => {
      if (error.message.includes('403') || error.message.includes('Authentication failed')) {
        // console.log('AI Assistant: Not retrying due to authentication error');
        return false;
      }
      return failureCount < 3;
    },
    // Improve resilience during login
    staleTime: 5 * 60 * 1000, // 5 minutes - keep data fresh but not too aggressive
    refetchOnWindowFocus: false, // Don't refetch on every window focus
    refetchOnMount: true, // Always refetch on mount for fresh data
  });

  // Add effect to log settings changes for debugging
  useEffect(() => {
    if (settings) {
      console.log('AI Assistant: Settings updated', {
        enable_ai_assistant: (settings as any)?.enable_ai_assistant,
        settingsData: settings
      });
    }
  }, [settings]);

  // Fetch AI configurations
  const { data: aiConfigs, isLoading: aiConfigsLoading } = useQuery({
    queryKey: ['ai-configs'],
    queryFn: () => api.get('/ai-config/'),
    enabled: !settingsLoading && !!(settings && (settings as any).enable_ai_assistant),
    retry: (failureCount, error) => {
      if (error.message.includes('403') || error.message.includes('Authentication failed')) {
        console.log('AI Configs: Not retrying due to authentication error');
        return false;
      }
      return failureCount < 3;
    },
  });

  // Fetch chat history when chat is opened
  useEffect(() => {
    if (isOpen && !historyLoaded && !settingsLoading && settings && (settings as any).enable_ai_assistant) {
      (async () => {
        try {
          const history = await api.get('/ai/chat/history');
          if (Array.isArray(history) && history.length > 0) {
            setMessages([
              ...history.map((msg: any, idx: number) => ({
                id: idx + 1,
                sender: msg.sender,
                text: msg.sender === 'ai' ? <EnhancedAIResponse text={msg.message} /> : msg.message
              }))
            ]);
          }
        } catch (e) {
          console.error('Failed to load AI chat history:', e);
        } finally {
          setHistoryLoaded(true);
        }
      })();
    }
  }, [isOpen, historyLoaded, settingsLoading, settings]);

  // Rest of the component hooks...
  const [recentMessages, setRecentMessages] = useState<Message[]>([]);
  const [isStreamingVisible, setIsStreamingVisible] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lastSuccessfulSubmissionRef = useRef<string>('');

  const [apiCallHistory, setApiCallHistory] = useState<ApiCall[]>([]);
  const [isThinking, setIsThinking] = useState(false);

  const addApiCall = useCallback((apiCall: ApiCall) => {
    setApiCallHistory(prev => [...prev, { ...apiCall, id: Date.now().toString() }]);
  }, []);

  const { toast } = useToast();

  // Effects for keyboard shortcuts etc.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        setIsFullscreen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen]);

  const { data: suggestedActions } = useQuery({
    queryKey: ['ai-suggested-actions'],
    queryFn: async () => {
      try {
        return await api.get('/ai/suggest-actions');
      } catch (error) {
        console.error('Failed to fetch suggested actions:', error);
        return [];
      }
    },
    enabled: !settingsLoading && !!(settings && (settings as any).enable_ai_assistant),
    retry: false,
  });

  // Conditional rendering checks - moved to the end after all hooks
  console.log('AI Assistant Debug:', { 
    settings, 
    settingsLoading, 
    settingsError, 
    isAIAssistantEnabled: !!(settings && (settings as any).enable_ai_assistant),
    aiConfigs,
    aiConfigsLoading,
    defaultAIConfig: aiConfigs && Array.isArray(aiConfigs) ? 
      (aiConfigs as any[]).find((config: any) => config.is_default && config.is_active) : 
      undefined,
    shouldRender: !settingsLoading && !!(settings && (settings as any).enable_ai_assistant) 
  });

  // CRITICAL: Add detailed logging for disabled state
  console.log('AI Assistant Render Decision:', {
    settingsLoading,
    settingsError: !!settingsError,
    settings: settings,
    isAIAssistantEnabled: !!(settings && (settings as any).enable_ai_assistant),
    rawSettingsValue: settings ? (settings as any).enable_ai_assistant : 'no settings',
    willRender: !settingsLoading && !!(settings && (settings as any).enable_ai_assistant)
  });

  const isAIAssistantEnabled = !!(settings && (settings as any).enable_ai_assistant);
  const defaultAIConfig = aiConfigs && Array.isArray(aiConfigs) ? 
    (aiConfigs as any[]).find((config: any) => config.is_default && config.is_active) : 
    undefined;

  // Handle different states more gracefully
  if (settingsLoading) {
    console.log('AI Assistant: Settings loading, showing minimal UI');
    // Don't hide completely while loading - show a minimal button that's disabled
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          variant="secondary"
          size="icon"
          className="h-12 w-12 rounded-full shadow-lg opacity-50 cursor-not-allowed"
          disabled
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      </div>
    );
  }

  // If there's a persistent error (not just temporary auth issues), default to hiding
  if (settingsError) {
    const errorMessage = settingsError.message || '';
    // Only hide for persistent errors, not temporary auth issues
    if (errorMessage.includes('Network Error') || errorMessage.includes('500')) {
      console.log('AI Assistant: Network/server error, hiding assistant:', settingsError);
      return null;
    } else {
      console.log('AI Assistant: Auth error but defaulting to show (will be handled by queries):', settingsError);
      // For auth errors, let the component try to render and individual queries will handle auth
    }
  }

  // Check if AI assistant should be shown
  if (!isAIAssistantEnabled) {
    console.log('AI Assistant: Not rendering because AI assistant is disabled', {
      settings,
      enable_ai_assistant: settings ? (settings as any).enable_ai_assistant : 'undefined',
      isAIAssistantEnabled,
      reason: 'enable_ai_assistant is false or settings is null'
    });
    return null;
  }

  console.log('AI Assistant: Rendering component - all checks passed');

  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (textToSend === '') return;

    const newMessage: Message = { id: messages.length + 1, sender: 'user', text: textToSend };
    setMessages((prev) => [...prev, newMessage]);
    if (!messageText) setInput('');

    // Show typing indicator
    const typingMessage: Message = { id: messages.length + 2, sender: 'ai', text: <EnhancedAIResponse text={t('aiAssistant.thinking')} /> };
    setMessages((prev) => [...prev, typingMessage]);

    // Get translated quick action texts (lowercase)
    const analyzePatternsText = t('aiAssistant.analyzePatterns').toLowerCase();
    const suggestActionsText = t('aiAssistant.suggestActions').toLowerCase();
    const paymentChartsText = t('aiAssistant.paymentCharts').toLowerCase();

    try {
      // Check for specific patterns that should use dedicated endpoints
      const lowerText = textToSend.toLowerCase();
      console.log('AI Assistant: Processing message:', { textToSend, lowerText });
      
      // Analyze Patterns: match translated or English keywords
      if (
        lowerText === analyzePatternsText ||
        lowerText.includes(analyzePatternsText) ||
        (lowerText.includes('analyze') && lowerText.includes('pattern'))
      ) {
        // Use the analyze-patterns endpoint (MCP-like functionality)
        console.log('AI Assistant: Using analyze-patterns endpoint');
        try {
          const response = await api.get('/ai/analyze-patterns') as any;
          console.log('AI Assistant: Analyze patterns response:', response);
          console.log('AI Assistant: Response success:', response.success);
          console.log('AI Assistant: Response data:', response.data);
          console.log('AI Assistant: Response error:', (response as any).error);
          
          if (response.success) {
            const data = response.data;
            // Format revenue by currency
            const formatRevenueByCurrency = (revenueData: any) => {
                if (!revenueData || Object.keys(revenueData).length === 0) {
                    return "None";
                }
                return Object.entries(revenueData)
                    .map(([currency, amount]) => `${currency} ${(amount as number).toFixed(2)}`)
                    .join(', ');
            };

            const analysisComponent = (
              <div className="space-y-4">
                <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-4 rounded-lg border border-blue-200">
                  <h3 className="text-lg font-bold text-blue-900 mb-3 flex items-center">
                    📊 {t('aiAssistant.invoicePatternAnalysis')}
                  </h3>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div className="bg-white p-3 rounded-lg shadow-sm">
                      <h4 className="font-semibold text-gray-800 mb-2">{t('aiAssistant.summary')}</h4>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.totalInvoices')}</span>
                          <span className="font-medium">{data.total_invoices}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.paidInvoices')}</span>
                          <span className="font-medium text-green-600">{data.paid_invoices}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.partiallyPaid')}</span>
                          <span className="font-medium text-yellow-600">{data.partially_paid_invoices || 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.unpaidInvoices')}</span>
                          <span className="font-medium text-red-600">{data.unpaid_invoices}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.overdueInvoices')}</span>
                          <span className="font-medium text-red-600">{data.overdue_invoices}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="bg-white p-3 rounded-lg shadow-sm">
                      <h4 className="font-semibold text-gray-800 mb-2">{t('aiAssistant.revenue')}</h4>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.totalRevenue')}</span>
                          <span className="font-medium text-green-600">{formatRevenueByCurrency(data.total_revenue_by_currency)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>{t('aiAssistant.outstanding')}</span>
                          <span className="font-medium text-orange-600">{formatRevenueByCurrency(data.outstanding_revenue_by_currency)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-gradient-to-r from-green-50 to-blue-50 p-3 rounded-lg border border-green-200">
                    <h4 className="font-semibold text-green-800 mb-2 flex items-center">
                      💡 Recommendations
                    </h4>
                    <ul className="space-y-1 text-sm">
                      {data.recommendations.map((rec: string, index: number) => (
                        <li key={index} className="flex items-start">
                          <span className="text-green-600 mr-2">•</span>
                          <span>{t(`recommendations.${rec}`)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            );

            setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: analysisComponent }]);
          } else {
            throw new Error('Failed to analyze patterns');
          }
        } catch (error) {
          console.error('AI Assistant: Error calling analyze-patterns:', error);
          console.error('AI Assistant: Error details:', {
            message: error.message,
            stack: error.stack,
            response: error.response
          });
          throw error;
        }
      } else if (
        lowerText === suggestActionsText ||
        lowerText.includes(suggestActionsText) ||
        (lowerText.includes('suggest') && lowerText.includes('action'))
      ) {
        // Use the suggest-actions endpoint
        console.log('AI Assistant: Using suggest-actions endpoint');
        try {
          const response = await api.get('/ai/suggest-actions') as any;
          console.log('AI Assistant: Suggest actions response:', response);
          
          if (response.success) {
            const data = response.data;
            const actionsComponent = (
              <div className="space-y-4">
                <div className="bg-gradient-to-r from-pink-50 to-purple-50 p-4 rounded-lg border border-pink-200">
                  <h3 className="text-lg font-bold text-pink-900 mb-3 flex items-center">
                    🎯 Suggested Actions
                  </h3>

                  <div className="space-y-3 mb-4">
                    {data.suggested_actions.map((action: any, index: number) => (
                      <div key={index} className="bg-white p-3 rounded-lg shadow-sm border-l-4 border-pink-400">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="font-semibold text-gray-800 mb-1">{action.action}</h4>
                            <p className="text-sm text-gray-600">{action.description}</p>
                          </div>
                          <div className="ml-3">
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              action.priority === 'high' ? 'bg-red-100 text-red-800' :
                              action.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {action.priority} priority
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-3 rounded-lg border border-blue-200">
                    <h4 className="font-semibold text-blue-800 mb-2 flex items-center">
                      📈 Quick Summary
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                      <div className="bg-white p-2 rounded text-center">
                        <div className="text-2xl font-bold text-red-600">{data.overdue_count}</div>
                        <div className="text-xs text-gray-600">{t('aiAssistant.overdueInvoices')}</div>
                      </div>
                      <div className="bg-white p-2 rounded text-center">
                        <div className="text-2xl font-bold text-orange-600">{data.clients_with_balance}</div>
                        <div className="text-xs text-gray-600">{t('aiAssistant.clientsWithBalance')}</div>
                      </div>
                      <div className="bg-white p-2 rounded text-center">
                        <div className="text-2xl font-bold text-blue-600">{data.recent_invoices_count}</div>
                        <div className="text-xs text-gray-600">{t('aiAssistant.recentInvoices')}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
            
            setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: actionsComponent }]);
          } else {
            throw new Error('Failed to get suggestions');
          }
        } catch (error) {
          console.error('AI Assistant: Error calling suggest-actions:', error);
          throw error;
        }
      } else if (
        lowerText === paymentChartsText ||
        lowerText.includes(paymentChartsText) ||
        lowerText.includes('payment') || lowerText.includes('payments')
      ) {
        // Handle payment data display with charts
        console.log('AI Assistant: Using payments endpoint with charts');
        try {
          const response = await api.get('/payments/') as any;
          console.log('AI Assistant: Payments response:', response);
          
          if (response.success && response.chart_data && Array.isArray(response.data)) {
            const paymentCharts = (
              <div className="mt-4">
                <PaymentCharts 
                  chartData={response.chart_data} 
                  payments={response.data} 
                />
              </div>
            );
            
            setMessages((prev) => [...prev.slice(0, -1), { 
              id: prev.length, 
              sender: 'ai', 
              text: (
                <div>
                  {paymentCharts}
                </div>
              )
            }]);
          } else {
            throw new Error('Failed to get payment data');
          }
        } catch (error) {
          console.error('AI Assistant: Error calling payments endpoint:', error);
          throw error;
        }
      } else {
        // Use the regular chat endpoint
        console.log('AI Assistant: Using chat endpoint');
        
        // Check if we have a default AI configuration
        if (!defaultAIConfig) {
          console.log('AI Assistant: No default AI config found:', { aiConfigs, defaultAIConfig });
          const errorMessage = t('settings.no_ai_config_found');
          setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: errorMessage }]);
          return;
        }
        
        const response = await api.post('/ai/chat', {
          message: textToSend,
          config_id: defaultAIConfig.id
        }) as any;

        if (response.success) {
          const aiResponse = response.data.response || response.data.message || "I'm sorry, I couldn't generate a response.";
          setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: <EnhancedAIResponse text={aiResponse} /> }]);
        } else {
          throw new Error('Failed to get AI response');
        }
      }
    } catch (error) {
      console.error("Error getting AI response:", error);
      const errorMessage = t("aiAssistant.error_message");
      setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: <EnhancedAIResponse text={errorMessage} /> }]);
    }
  };

  const handleQuickAction = (action: string) => {
    // Automatically send the message when quick action is clicked
    handleSendMessage(action);
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <TooltipProvider>
        <div>
          <Button
            className="rounded-full w-20 h-20 shadow-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 hover:scale-105 transition-transform duration-200 border-4 border-white/40 backdrop-blur-lg"
            style={{ boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)' }}
            onClick={() => setIsOpen(true)}
          >
            <Bot className="h-10 w-10 text-white drop-shadow-lg" />
          </Button>
          
          {isOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center">
              {/* Backdrop */}
              <div 
                className="absolute inset-0 bg-black/20 backdrop-blur-sm"
                onClick={() => setIsOpen(false)}
              />
              
              {/* Dialog */}
              <div className={`relative w-full flex flex-col p-0 bg-white shadow-2xl border-0 overflow-hidden animate-fade-in rounded-3xl ${
                isFullscreen 
                  ? 'max-w-[95vw] h-[95vh] max-h-[95vh]' 
                  : 'max-w-[600px] h-[80vh] max-h-[800px]'
              }`}>
                <div className="relative p-6 flex items-center justify-between shadow-md overflow-hidden rounded-t-3xl z-20 bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500">
                  <div className="relative flex items-center gap-4 z-20">
                    <div className="bg-white/20 rounded-full p-2 shadow-lg">
                      <Bot className="h-8 w-8 text-white" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-white drop-shadow">{t('aiAssistant.title')}</h2>
                      <p className="text-white/80 text-sm mt-1">{t('aiAssistant.askAnything')}</p>
                    </div>
                  </div>
                  <div className="relative flex items-center gap-2 z-20">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={toggleFullscreen}
                      className="text-white hover:text-white/90 hover:bg-white/30 rounded-lg p-2.5 transition-all duration-200 border border-white/20 shadow-lg backdrop-blur-sm"
                      title={isFullscreen ? t('aiAssistant.exitFullscreen') : t('aiAssistant.enterFullscreen')}
                    >
                      {isFullscreen ? (
                        <Minimize2 className="h-5 w-5 drop-shadow-sm" />
                      ) : (
                        <Maximize2 className="h-5 w-5 drop-shadow-sm" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsOpen(false)}
                      className="text-white hover:text-white/90 hover:bg-white/30 rounded-lg p-2.5 transition-all duration-200 border border-white/20 shadow-lg backdrop-blur-sm"
                      title={t('aiAssistant.closeChat')}
                    >
                      <X className="h-5 w-5 drop-shadow-sm" />
                    </Button>
                  </div>
                </div>
                {/* Retention notice */}
                {(() => {
                  const s = settings as any;
                  return s && typeof s.ai_chat_history_retention_days === 'number' ? (
                    <div className="px-6 pt-2 pb-1 text-xs text-muted-foreground text-center">
                      {t('aiAssistant.chatHistoryRetentionNotice', { days: s.ai_chat_history_retention_days })}
                    </div>
                  ) : null;
                })()}
                <ScrollArea ref={scrollAreaRef} className="flex-grow px-6 py-4 overflow-y-auto relative z-20">
                  <div className="flex flex-col space-y-4">
                    {messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`max-w-[80%] transition-all duration-200 ${msg.sender === 'user' ? 'bg-blue-100 text-blue-900 self-end px-4 py-3 rounded-2xl shadow-md' : 'bg-gray-100 text-gray-900 self-start px-4 py-3 rounded-2xl shadow-md'}`}
                        style={{ wordBreak: 'break-word', whiteSpace: 'pre-line' }}
                      >
                        {msg.sender === 'user' ? (
                          <div>
                            {msg.text}
                          </div>
                        ) : (
                          typeof msg.text === 'string' ? (
                            <EnhancedAIResponse text={msg.text} />
                          ) : (
                            msg.text
                          )
                        )}
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </div>
                </ScrollArea>
                <div className="flex space-x-2 px-6 pb-3 pt-2 relative z-20">
                  <Button
                    variant="outline"
                    className="rounded-xl bg-gradient-to-r from-blue-100 to-purple-100 text-blue-700 font-semibold shadow hover:from-blue-200 hover:to-purple-200"
                    onClick={() => handleQuickAction(t('aiAssistant.analyzePatterns'))}
                  >
                    {t('aiAssistant.analyzePatterns')}
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-xl bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700 font-semibold shadow hover:from-pink-200 hover:to-purple-200"
                    onClick={() => handleQuickAction(t('aiAssistant.suggestActions'))}
                  >
                    {t('aiAssistant.suggestActions')}
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-xl bg-gradient-to-r from-green-100 to-blue-100 text-green-700 font-semibold shadow hover:from-green-200 hover:to-blue-200"
                    onClick={() => handleQuickAction(t('aiAssistant.paymentCharts'))}
                  >
                    {t('aiAssistant.paymentCharts')}
                  </Button>
                </div>
                <div className="flex items-center px-6 pb-6 pt-2 gap-2 relative z-20">
                  <Input
                    placeholder={t('aiAssistant.inputPlaceholder')}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        handleSendMessage();
                      }
                    }}
                    className="flex-grow rounded-xl bg-white/80 border border-gray-300 shadow focus:ring-2 focus:ring-blue-400 focus:border-blue-400 text-lg px-4 py-3"
                  />
                  <Button
                    className="rounded-full w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-500 text-white shadow-lg hover:scale-105 transition-transform duration-200 flex items-center justify-center"
                    onClick={() => handleSendMessage()}
                  >
                    <Send className="h-6 w-6" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </TooltipProvider>
    </div>
  );
});

export default AIAssistant;
