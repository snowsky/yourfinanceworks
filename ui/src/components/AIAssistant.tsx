import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageCircle, Send, Sparkles, Zap, CheckCircle, AlertCircle, BarChart3, Lightbulb, Target, Loader } from 'lucide-react';
import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import PaymentCharts from './PaymentCharts';
import { useTranslation } from 'react-i18next';

// Debug toggle for AI Assistant logs (set VITE_DEBUG_AI_ASSISTANT=true to enable)
const DEBUG_AI_ASSISTANT = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_DEBUG_AI_ASSISTANT === 'true');

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string | React.ReactNode;
  timestamp?: string;
}

// --- Helper Components for Rich UI ---

const InvoiceAnalysisCard = ({ data }: { data: any }) => {
  const { t } = useTranslation();

  const formatRevenueByCurrency = (revenueData: any) => {
    if (!revenueData || Object.keys(revenueData).length === 0) {
      return "None";
    }
    return Object.entries(revenueData)
      .map(([currency, amount]) => `${currency} ${(amount as number).toFixed(2)}`)
      .join(', ');
  };

  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/10 dark:to-purple-900/10 p-4 rounded-2xl border border-blue-200/50 dark:border-blue-800/30">
        <h3 className="text-lg font-bold text-blue-900 dark:text-blue-200 mb-3 flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          {t('aiAssistant.invoicePatternAnalysis')}
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className="bg-white/80 dark:bg-black/30 backdrop-blur-sm p-3 rounded-xl shadow-sm border border-border/50">
            <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{t('aiAssistant.summary')}</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.totalInvoices')}</span>
                <span className="font-medium text-foreground">{data.total_invoices}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.paidInvoices')}</span>
                <span className="font-medium text-emerald-600 dark:text-emerald-400">{data.paid_invoices}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.partiallyPaid')}</span>
                <span className="font-medium text-amber-600 dark:text-amber-400">{data.partially_paid_invoices || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.unpaidInvoices')}</span>
                <span className="font-medium text-red-600 dark:text-red-400">{data.unpaid_invoices}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.overdueInvoices')}</span>
                <span className="font-medium text-rose-600 dark:text-rose-400">{data.overdue_invoices}</span>
              </div>
            </div>
          </div>

          <div className="bg-white/80 dark:bg-black/30 backdrop-blur-sm p-3 rounded-xl shadow-sm border border-border/50">
            <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{t('aiAssistant.revenue')}</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.totalRevenue')}</span>
                <span className="font-medium text-emerald-600 dark:text-emerald-400">{formatRevenueByCurrency(data.total_revenue_by_currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.outstanding')}</span>
                <span className="font-medium text-orange-600 dark:text-orange-400">{formatRevenueByCurrency(data.outstanding_revenue_by_currency)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-emerald-50 to-blue-50 dark:from-emerald-900/10 dark:to-blue-900/10 p-3 rounded-xl border border-emerald-200/50 dark:border-emerald-800/30">
          <h4 className="font-semibold text-emerald-800 dark:text-emerald-300 mb-2 flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            Recommendations
          </h4>
          <ul className="space-y-2 text-sm">
            {data.recommendations.map((rec: string, index: number) => (
              <li key={index} className="flex items-start text-emerald-900 dark:text-emerald-200">
                <span className="text-emerald-500 mr-2 mt-0.5">•</span>
                <span>{t(`recommendations.${rec}`)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

const SuggestedActionsCard = ({ data }: { data: any }) => {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-br from-pink-50 to-purple-50 dark:from-pink-900/10 dark:to-purple-900/10 p-4 rounded-2xl border border-pink-200/50 dark:border-pink-800/30">
        <h3 className="text-lg font-bold text-pink-900 dark:text-pink-200 mb-3 flex items-center gap-2">
          <Target className="h-5 w-5" />
          🎯 Suggested Actions
        </h3>

        <div className="space-y-3 mb-4">
          {data.suggested_actions.map((action: any, index: number) => (
            <div key={index} className="bg-white/80 dark:bg-black/30 backdrop-blur-sm p-3 rounded-xl shadow-sm border-l-4 border-pink-400">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-1">{action.action}</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{action.description}</p>
                </div>
                <div className="ml-3">
                  <Badge variant="outline" className={`${action.priority === 'high' ? 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800' :
                    action.priority === 'medium' ? 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800' :
                      'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800'
                    }`}>
                    {action.priority}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/10 dark:to-purple-900/10 p-3 rounded-xl border border-blue-200/50 dark:border-blue-800/30">
          <h4 className="font-semibold text-blue-800 dark:text-blue-300 mb-2 flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Quick Summary
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div className="bg-white/60 dark:bg-black/20 p-2 rounded-lg text-center backdrop-blur-sm">
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">{data.overdue_count}</div>
              <div className="text-xs text-muted-foreground">{t('aiAssistant.overdueInvoices')}</div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 p-2 rounded-lg text-center backdrop-blur-sm">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">{data.clients_with_balance}</div>
              <div className="text-xs text-muted-foreground">{t('aiAssistant.clientsWithBalance')}</div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 p-2 rounded-lg text-center backdrop-blur-sm">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{data.recent_invoices_count}</div>
              <div className="text-xs text-muted-foreground">{t('aiAssistant.recentInvoices')}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const PaymentChartsCard = ({ data }: { data: any }) => {
  return (
    <div className="mt-4">
      <PaymentCharts
        chartData={data.chart_data}
        payments={data.data}
      />
    </div>
  );
};

// --- Markdown Rendering Helper ---
const MarkdownRenderer = ({ content }: { content: string }) => {
  if (!content) return null;

  // Simple Markdown parsing:
  // 1. Split by newlines to preserve formatting
  // 2. Handle bold (**text**)
  // 3. Handle bullet points (* item or - item)
  // 4. Handle headers (### or **Header**) -> usually mapped to bold in chat

  const sections = content.split('\n');

  return (
    <div className="space-y-1 text-[0.95rem] leading-relaxed">
      {sections.map((line, idx) => {
        // Handle headers / bold lines
        const isHeader = line.startsWith('**') && line.endsWith('**') || line.startsWith('### ');

        // Handle Bullet Points
        const isBullet = line.trim().startsWith('* ') || line.trim().startsWith('- ') || line.trim().startsWith('• ');

        // Process inline bolding: replace **text** with <strong>text</strong>
        // We need to split properly avoiding simple regex HTML injection, but for React we can parse parts.
        const processInlineBold = (text: string) => {
          const parts = text.split(/(\*\*.*?\*\*)/g);
          return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={i} className="font-bold text-indigo-900 dark:text-indigo-100">{part.slice(2, -2)}</strong>;
            }
            return part;
          });
        };

        if (isBullet) {
          const bulletContent = line.replace(/^[\*\-\•]\s*/, '');
          return (
            <div key={idx} className="flex items-start text-foreground/90 ml-2">
              <span className="mr-2 mt-1.5 h-1.5 w-1.5 rounded-full bg-indigo-500/50 shrink-0"></span>
              <span>{processInlineBold(bulletContent)}</span>
            </div>
          );
        }

        if (isHeader) {
          const headerContent = line.replace(/^###\s+/, '').replace(/^\*\*/, '').replace(/\*\*$/, '');
          return (
            <div key={idx} className="font-bold text-lg text-indigo-950 dark:text-indigo-50 mt-2 mb-1">
              {headerContent}
            </div>
          );
        }

        // Standard line - if empty, render spacing
        if (!line.trim()) {
          return <div key={idx} className="h-2"></div>;
        }

        return (
          <div key={idx} className="whitespace-pre-wrap">
            {processInlineBold(line)}
          </div>
        );
      })}
    </div>
  );
};


// Styled AI Response Component
const StyledAIResponse = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-white/50 dark:bg-black/20 backdrop-blur-sm p-4 rounded-2xl border border-border/50 shadow-sm">
    <div className="flex items-start gap-3">
      <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full p-2 shadow-sm shrink-0">
        <Sparkles className="h-4 w-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-foreground leading-relaxed text-[0.95rem]">
          {children}
        </div>
      </div>
    </div>
  </div>
);

// Format timestamp to user-friendly time with date and timezone support
const formatMessageTime = (dateString?: string, timezone?: string) => {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    const options: Intl.DateTimeFormatOptions = {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    };
    if (timezone) {
      options.timeZone = timezone;
    }
    return date.toLocaleString([], options);
  } catch (e) {
    return '';
  }
};

// Enhanced AI Response with different styles based on content
const EnhancedAIResponse = ({ text }: { text: string }) => {
  // 1. Try to parse as JSON for rich content
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object') {
      if (parsed.type === 'analysis_patterns') {
        return <InvoiceAnalysisCard data={parsed.data} />;
      }
      if (parsed.type === 'suggested_actions') {
        return <SuggestedActionsCard data={parsed.data} />;
      }
      if (parsed.type === 'payment_charts') {
        return <PaymentChartsCard data={parsed.data} />;
      }
    }
  } catch (e) {
    // Not JSON, continue to string parsing
  }

  // 2. Regular Text parsing
  const lowerText = text.toLowerCase();

  // Create formatted content using MarkdownRenderer
  const content = <MarkdownRenderer content={text} />;

  if (lowerText.includes('error') || lowerText.includes('sorry') || lowerText.includes('failed')) {
    return (
      <div className="bg-red-50/50 dark:bg-red-900/10 backdrop-blur-sm p-4 rounded-2xl border border-red-200/50 dark:border-red-800/30">
        <div className="flex items-start gap-3">
          <div className="bg-gradient-to-br from-red-500 to-pink-600 rounded-full p-2 shadow-sm shrink-0">
            <AlertCircle className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-red-800 dark:text-red-200 leading-relaxed font-medium text-[0.95rem]">
              {content}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (lowerText.includes('success') || lowerText.includes('great') || lowerText.includes('excellent')) {
    return (
      <div className="bg-emerald-50/50 dark:bg-emerald-900/10 backdrop-blur-sm p-4 rounded-2xl border border-emerald-200/50 dark:border-emerald-800/30">
        <div className="flex items-start gap-3">
          <div className="bg-gradient-to-br from-emerald-500 to-green-600 rounded-full p-2 shadow-sm shrink-0">
            <CheckCircle className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-emerald-800 dark:text-emerald-200 leading-relaxed font-medium text-[0.95rem]">
              {content}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (lowerText.includes('configuration') || lowerText.includes('settings')) {
    return (
      <div className="bg-blue-50/50 dark:bg-blue-900/10 backdrop-blur-sm p-4 rounded-2xl border border-blue-200/50 dark:border-blue-800/30">
        <div className="flex items-start gap-3">
          <div className="bg-gradient-to-br from-blue-500 to-cyan-600 rounded-full p-2 shadow-sm shrink-0">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-blue-800 dark:text-blue-200 leading-relaxed text-[0.95rem]">
              {content}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Default styled response
  return <StyledAIResponse>{content}</StyledAIResponse>;
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
    };

    checkAuth();

    // Check authentication on localStorage changes
    const handleStorageChange = (e: StorageEvent) => {
      // If token is removed, immediately hide AI assistant
      if (e.key === 'token' && !e.newValue) {
        setIsAuthenticated(false);
        setUser(null);
        setIsAdminUser(false);
        return;
      }
      // If user data is removed, hide assistant
      if (e.key === 'user' && !e.newValue) {
        setIsAuthenticated(false);
        setUser(null);
        setIsAdminUser(false);
        return;
      }
      // If token or user is added (login), immediately check auth
      if ((e.key === 'token' && e.newValue) || (e.key === 'user' && e.newValue)) {
        setTimeout(checkAuth, 100); // Small delay to ensure both token and user are set
        return;
      }
      checkAuth();
    };

    // Listen for storage events (from other tabs)
    window.addEventListener('storage', handleStorageChange);

    // Listen for logout events
    const handleLogout = () => {
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
          setIsAuthenticated(false);
          setUser(null);
          setIsAdminUser(false);
        }
      } else if (!isAuthenticated) {
        // If credentials exist but we think user is not authenticated, recheck
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
    return null;
  }

  // If authenticated and admin, render the AI assistant
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
  const [hasUnreadMessages, setHasUnreadMessages] = useState(() => {
    // Check localStorage for persisted unread state, default to true only on first visit
    const stored = localStorage.getItem('ai-assistant-unread');
    return stored === null ? true : stored === 'true';
  });
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [justLoadedHistory, setJustLoadedHistory] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Helper to update the last AI message (thinking indicator) with actual content
  const updateAiMessage = useCallback((content: React.ReactNode | string) => {
    setMessages((prev) => {
      const updated = [...prev.slice(0, -1), {
        id: prev.length,
        sender: 'ai' as const,
        text: typeof content === 'string' ? <EnhancedAIResponse text={content} /> : content,
        timestamp: new Date().toISOString()
      }];
      if (!isOpen) {
        setHasUnreadMessages(true);
        localStorage.setItem('ai-assistant-unread', 'true');
      }
      return updated;
    });
    setIsThinking(false);
    setIsGenerating(false);
  }, [isOpen]);

  // Auto-scroll to bottom when messages change (but not when loading history)
  const scrollToBottom = useCallback(() => {
    // Use setTimeout to ensure DOM has updated
    setTimeout(() => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, 100);
  }, []);

  useEffect(() => {
    // Only scroll to bottom on initial load or when new messages are added (not when loading history)
    // We can detect new messages by checking if the last message is newer than what we had before
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      const isNewMessage = !isLoadingMore && !justLoadedHistory;

      if (isInitialLoad || isNewMessage) {
        scrollToBottom();
        if (isInitialLoad) {
          setIsInitialLoad(false);
        }
      }
    }

    // Reset the flag after processing
    setJustLoadedHistory(false);
  }, [messages, scrollToBottom, isInitialLoad, isLoadingMore]);

  // Fetch user settings to check the enable_ai_assistant flag (only for admin users)
  const { data: settings, isLoading: settingsLoading, error: settingsError, refetch: refetchSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings/'),
    refetchInterval: (query) => {
      // Stop refetching if there's an authentication error
      if (query.state.error &&
        (query.state.error.message.includes('403') ||
          query.state.error.message.includes('Authentication failed'))) {
        return false;
      }
      // Only refetch if AI assistant is not explicitly disabled
      const currentSettings = query.state.data;
      return currentSettings && !(currentSettings as any)?.enable_ai_assistant ? false : 30000;
    },
    retry: (failureCount, error) => {
      if (error.message.includes('403') || error.message.includes('Authentication failed')) {
        return false;
      }
      return failureCount < 3;
    },
    // Improve resilience during login
    staleTime: 5 * 60 * 1000, // 5 minutes - keep data fresh but not too aggressive
    refetchOnWindowFocus: false, // Don't refetch on every window focus
    refetchOnMount: true, // Always refetch on mount for fresh data
  });

  // Fetch AI configurations - only when AI assistant is open
  const { data: aiConfigs, isLoading: aiConfigsLoading } = useQuery({
    queryKey: ['ai-configs'],
    queryFn: () => api.get('/ai-config/'),
    enabled: isOpen && !settingsLoading && !!(settings && (settings as any).enable_ai_assistant),
    retry: (failureCount, error) => {
      if (error.message.includes('403') || error.message.includes('Authentication failed')) {
        return false;
      }
      return failureCount < 3;
    },
  });

  // Fetch chat history when chat is opened
  useEffect(() => {
    if (isOpen && !settingsLoading && settings && (settings as any).enable_ai_assistant) {
      (async () => {
        try {
          // Load the last 20 messages (offset 0 = most recent)
          const history = await api.get('/ai/chat/history?limit=20&offset=0') as any[];
          if (Array.isArray(history) && history.length > 0) {
            const loadedMessages = history.map((msg: any, idx: number) => ({
              id: idx + 1,
              sender: msg.sender,
              text: msg.sender === 'ai' ? <EnhancedAIResponse text={msg.message} /> : msg.message,
              timestamp: msg.created_at
            }));
            setMessages(loadedMessages);
            setHistoryOffset(20);
            // If we got less than 20 messages, there's no more history
            setHasMoreHistory(history.length === 20);
            setHistoryLoaded(true);
            // Force scroll to bottom after a delay to ensure DOM is ready
            setTimeout(() => {
              if (messagesEndRef.current) {
                messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
              }

              // Also try scrolling the ScrollArea viewport directly as fallback
              const scrollArea = document.querySelector('[data-radix-scroll-area-viewport]');
              if (scrollArea) {
                scrollArea.scrollTop = scrollArea.scrollHeight;
              }
            }, 200);
          } else {
            // No history, show welcome message
            setMessages([{ id: 1, sender: 'ai', text: <EnhancedAIResponse text={t('aiAssistant.welcomeMessage')} /> }]);
            setHistoryOffset(0);
            setHasMoreHistory(false);
            setHistoryLoaded(true);
            // Force scroll to bottom for welcome message too
            setTimeout(() => {
              if (messagesEndRef.current) {
                messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
              }

              const scrollArea = document.querySelector('[data-radix-scroll-area-viewport]');
              if (scrollArea) {
                scrollArea.scrollTop = scrollArea.scrollHeight;
              }
            }, 200);
          }
        } catch (e) {
          console.error('Failed to load AI chat history:', e);
          // On error, show welcome message
          setMessages([{ id: 1, sender: 'ai', text: <EnhancedAIResponse text={t('aiAssistant.welcomeMessage')} /> }]);
          setHistoryOffset(0);
          setHasMoreHistory(false);
          setHistoryLoaded(true);
          // Force scroll to bottom for error case too
          setTimeout(() => {
            if (messagesEndRef.current) {
              messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
            }

            const scrollArea = document.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollArea) {
              scrollArea.scrollTop = scrollArea.scrollHeight;
            }
          }, 200);
        }
      })();
    }
  }, [isOpen, settingsLoading, settings, t]);

  // Rest of the component hooks...
  const [isStreamingVisible, setIsStreamingVisible] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isThinking, setIsThinking] = useState(false);

  // Reset loading states when modal closes
  useEffect(() => {
    if (!isOpen) {
      setIsGenerating(false);
      setIsThinking(false);
      setIsStreamingVisible(false);
      setHistoryLoaded(false); // Reset history loaded so it reloads when dialog opens again
      setHistoryOffset(0);
      setHasMoreHistory(true);
      setIsLoadingMore(false);
      setJustLoadedHistory(false);
      setIsInitialLoad(true);
    } else {
      // Clear unread indicator when opened
      setHasUnreadMessages(false);
      localStorage.setItem('ai-assistant-unread', 'false');
    }
  }, [isOpen]);

  // Handle loading more history
  const handleLoadMoreHistory = useCallback(async () => {
    if (isLoadingMore || !hasMoreHistory || !historyLoaded) return;

    if (DEBUG_AI_ASSISTANT) console.log('Loading more history...');
    setIsLoadingMore(true);
    try {
      const moreHistory = await api.get(`/ai/chat/history?limit=20&offset=${historyOffset}`) as any[];
      if (DEBUG_AI_ASSISTANT) console.log('Loaded more history:', moreHistory.length, 'messages');

      if (Array.isArray(moreHistory) && moreHistory.length > 0) {
        // Reverse the batch since backend returns in descending order (newest first)
        // but we want to prepend in chronological order (oldest first)
        const reversedHistory = moreHistory.reverse();

        const newMessages = reversedHistory.map((msg: any, idx: number) => ({
          id: messages.length + idx + 1,
          sender: msg.sender,
          text: msg.sender === 'ai' ? <EnhancedAIResponse text={msg.message} /> : msg.message,
          timestamp: msg.created_at
        }));

        // Mark that we just loaded history so scrollToBottom won't trigger
        setJustLoadedHistory(true);

        // Prepend new messages to the beginning
        setMessages(prev => [...newMessages, ...prev]);
        setHistoryOffset(prev => prev + 20);

        // If we got less than 20 messages, we've reached the end
        if (moreHistory.length < 20) {
          setHasMoreHistory(false);
          if (DEBUG_AI_ASSISTANT) console.log('Reached end of history');
        }
      } else {
        setHasMoreHistory(false);
        if (DEBUG_AI_ASSISTANT) console.log('No more history available');
      }
    } catch (e) {
      console.error('Failed to load more chat history:', e);
      setHasMoreHistory(false);
    } finally {
      setIsLoadingMore(false);
    }
  }, [hasMoreHistory, isLoadingMore, historyLoaded, historyOffset, messages.length]);

  // Set up Intersection Observer for loading more history when scrolling to top
  useEffect(() => {
    if (!sentinelRef.current || !historyLoaded) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (DEBUG_AI_ASSISTANT) {
          console.log('Sentinel intersection:', entries[0].isIntersecting, { hasMoreHistory, isLoadingMore, historyLoaded });
        }

        // If sentinel is visible and we have more history to load
        if (entries[0].isIntersecting && hasMoreHistory && !isLoadingMore && historyLoaded) {
          if (DEBUG_AI_ASSISTANT) console.log('Sentinel visible - loading more history...');
          handleLoadMoreHistory();
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasMoreHistory, isLoadingMore, historyLoaded, handleLoadMoreHistory]);

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

  const isAIAssistantEnabled = !!(settings && (settings as any).enable_ai_assistant);
  const aiAssistantLicenseError = (settings as any)?.ai_assistant_license_error;
  const defaultAIConfig = aiConfigs && Array.isArray(aiConfigs) ?
    (aiConfigs as any[]).find((config: any) => config.is_default && config.is_active) :
    undefined;

  // Handle different states more gracefully
  if (settingsLoading) {
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
      if (DEBUG_AI_ASSISTANT) console.log('AI Assistant: Network/server error, hiding assistant:', settingsError);
      return null;
    } else {
      if (DEBUG_AI_ASSISTANT) console.log('AI Assistant: Auth error but defaulting to show (will be handled by queries):', settingsError);
      // For auth errors, let the component try to render and individual queries will handle auth
    }
  }

  // Check if AI assistant should be shown
  if (!isAIAssistantEnabled) {
    // Show license error message if AI assistant is disabled due to license issues
    if (aiAssistantLicenseError) {
      if (DEBUG_AI_ASSISTANT) {
        console.log('AI Assistant: Not rendering due to license error', {
          settings,
          aiAssistantLicenseError,
          reason: 'License expired or deactivated'
        });
      }
      return (
        <div className="fixed bottom-4 right-4 z-50">
          <Button
            variant="secondary"
            size="icon"
            className="h-12 w-12 rounded-full shadow-lg opacity-75 cursor-not-allowed"
            disabled
            title={aiAssistantLicenseError}
          >
            <MessageCircle className="h-6 w-6" />
          </Button>
        </div>
      );
    }
    
    if (DEBUG_AI_ASSISTANT) {
      console.log('AI Assistant: Not rendering because AI assistant is disabled', {
        settings,
        enable_ai_assistant: settings ? (settings as any).enable_ai_assistant : 'undefined',
        isAIAssistantEnabled,
        reason: 'enable_ai_assistant is false or settings is null'
      });
    }
    return null;
  }

  if (DEBUG_AI_ASSISTANT) console.log('AI Assistant: Rendering component - all checks passed');

  // Separate API client for AI requests to avoid interfering with global loading states
  const aiApiRequest = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('token');
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        return user.tenant_id?.toString();
      } catch { return undefined; }
    })();

    const requestUrl = url.startsWith('http') ? url : `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}${url}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...(tenantId && { 'X-Tenant-ID': tenantId }),
    };

    const response = await fetch(requestUrl, {
      ...options,
      headers: { ...headers, ...options.headers },
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = 'Request failed';
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return response.json();
  };

  // Helper function to save chat messages
  const saveChatMessage = async (message: string, sender: 'user' | 'ai') => {
    try {
      await aiApiRequest('/ai/chat/message', {
        method: 'POST',
        body: JSON.stringify({
          message,
          sender
        })
      });
    } catch (error) {
      console.error(`Failed to save ${sender} message:`, error);
    }
  };


  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (textToSend === '') return;

    const newMessage: Message = {
      id: messages.length + 1,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, newMessage]);
    if (!messageText) setInput('');

    // Save user message to backend
    await saveChatMessage(textToSend, 'user');

    // Show typing indicator
    setIsThinking(true);
    setIsGenerating(true);
    const typingMessage: Message = {
      id: messages.length + 2,
      sender: 'ai',
      text: <EnhancedAIResponse text={t('aiAssistant.thinking')} />,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, typingMessage]);

    // Get translated quick action texts (lowercase)
    const analyzePatternsText = t('aiAssistant.analyzePatterns').toLowerCase();
    const suggestActionsText = t('aiAssistant.suggestActions').toLowerCase();
    const paymentChartsText = t('aiAssistant.paymentCharts').toLowerCase();

    try {
      // Check for specific patterns that should use dedicated endpoints
      const lowerText = textToSend.toLowerCase();
      // Analyze Patterns: match translated or English keywords
      if (
        lowerText === analyzePatternsText ||
        lowerText.includes(analyzePatternsText) ||
        (lowerText.includes('analyze') && lowerText.includes('pattern'))
      ) {
        const response = await aiApiRequest('/ai/analyze-patterns') as any;
        if (response.success) {
          const data = response.data;
          await saveChatMessage(JSON.stringify({ type: 'analysis_patterns', data }), 'ai');
          updateAiMessage(<InvoiceAnalysisCard data={data} />);
        } else {
          throw new Error('Failed to analyze patterns');
        }
      } else if (
        lowerText === suggestActionsText ||
        lowerText.includes(suggestActionsText) ||
        (lowerText.includes('suggest') && lowerText.includes('action'))
      ) {
        const response = await aiApiRequest('/ai/suggest-actions') as any;
        if (response.success) {
          const data = response.data;
          await saveChatMessage(JSON.stringify({ type: 'suggested_actions', data }), 'ai');
          updateAiMessage(<SuggestedActionsCard data={data} />);
        } else {
          throw new Error('Failed to get suggestions');
        }
      } else if (
        lowerText === paymentChartsText ||
        lowerText.includes(paymentChartsText) ||
        (lowerText.includes('payment') || lowerText.includes('payments')) &&
        !lowerText.includes('expense') && !lowerText.includes('statement')
      ) {
        // Handle payment data display with charts
        const response = await aiApiRequest('/payments/') as any;
        if (response.success && response.chart_data && Array.isArray(response.data)) {
          await saveChatMessage(JSON.stringify({ type: 'payment_charts', data: response }), 'ai');
          updateAiMessage(<PaymentChartsCard data={response} />);
        } else {
          throw new Error('Failed to get payment data');
        }
      } else if (
        lowerText.includes('expense') || lowerText.includes('expenses') ||
        lowerText.includes('list expenses') || lowerText.includes('show expenses')
      ) {
        const response = await api.post('/ai/chat', {
          message: textToSend,
          config_id: defaultAIConfig?.id || 0
        }) as any;
        if (response.success) {
          const aiResponse = response.data.response || response.data.message || "I'm sorry, I couldn't generate a response.";
          await saveChatMessage(aiResponse, 'ai');
          updateAiMessage(aiResponse);
        } else {
          throw new Error(response.error || 'Failed to get AI response');
        }
      } else if (
        lowerText.includes('statement') || lowerText.includes('statements') ||
        lowerText.includes('bank statement') || lowerText.includes('show statements') ||
        lowerText.includes('list statements')
      ) {
        const response = await api.post('/ai/chat', {
          message: textToSend,
          config_id: defaultAIConfig?.id || 0
        }) as any;
        if (response.success) {
          const aiResponse = response.data.response || response.data.message || "I'm sorry, I couldn't generate a response.";
          await saveChatMessage(aiResponse, 'ai');
          updateAiMessage(aiResponse);
        } else {
          throw new Error(response.error || 'Failed to get AI response');
        }
      } else {
        const response = await aiApiRequest('/ai/chat', {
          method: 'POST',
          body: JSON.stringify({ message: textToSend, config_id: defaultAIConfig?.id || 0 })
        }) as any;
        if (response.success) {
          const aiResponse = response.data.response || response.data.message || "I'm sorry, I couldn't generate a response.";
          await saveChatMessage(aiResponse, 'ai');
          updateAiMessage(aiResponse);
        } else {
          throw new Error(response.error || 'Failed to get AI response');
        }
      }
    } catch (error) {
      console.error("Error getting AI response:", error);
      const errorMessage = t("aiAssistant.error_message");
      setMessages((prev) => {
        const updated = [...prev.slice(0, -1), {
          id: prev.length,
          sender: 'ai' as const,
          text: <EnhancedAIResponse text={errorMessage} />,
          timestamp: new Date().toISOString()
        }];
        if (!isOpen) {
          setHasUnreadMessages(true);
          localStorage.setItem('ai-assistant-unread', 'true');
        }
        return updated;
      });
      setIsThinking(false);
      setIsGenerating(false);
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
      <div>
        <Button
          className={cn(
            "rounded-full w-16 h-16 shadow-[0_8px_30px_rgb(0,0,0,0.12)] hover:shadow-[0_12px_40px_rgb(0,0,0,0.18)]",
            "bg-gradient-to-br from-[#2b5876] via-[#4e4376] to-[#2b5876] dark:from-indigo-600 dark:via-purple-600 dark:to-indigo-600",
            "hover:scale-105 transition-all duration-300 border border-white/10 backdrop-blur-md transform-gpu",
            isOpen ? "scale-0 opacity-0" : "scale-100 opacity-100"
          )}
          onClick={() => setIsOpen(true)}
        >
          <MessageCircle className="h-8 w-8 text-white drop-shadow-md" />
          {hasUnreadMessages && (
            <span className="absolute -top-1 -right-1 flex h-3 w-3 pointer-events-none">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
          )}
        </Button>

        {isOpen && (
          <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-6">
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm transform-gpu will-change-transform"
              onClick={() => setIsOpen(false)}
            />

            {/* Dialog Panel */}
            <div className={cn(
              "relative flex flex-col bg-white/95 dark:bg-gray-950/95 w-full shadow-2xl overflow-hidden transform-gpu will-change-transform",
              "backdrop-blur-xl border border-white/20 dark:border-white/10",
              isFullscreen
                ? 'h-[100dvh] w-full sm:rounded-none'
                : 'h-[85vh] sm:h-[800px] max-h-[800px] sm:w-[500px] sm:rounded-[2rem] rounded-t-[2rem]'
            )}>

              {/* Header */}
              <div className="relative shrink-0 p-4 sm:p-6 flex items-center justify-between z-20">
                {/* Glass Header Background */}
                <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-[#4e4376]/10 to-transparent pointer-events-none" />

                <div className="relative flex items-center gap-4 z-20">
                  <div className="bg-gradient-to-br from-[#2b5876] to-[#4e4376] rounded-2xl p-2.5 shadow-lg shadow-indigo-500/20 ring-1 ring-white/20">
                    <MessageCircle className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300">
                      {t('aiAssistant.title')}
                    </h2>
                    <div className="flex items-center gap-1.5">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                      </span>
                      <p className="text-muted-foreground text-xs font-medium">Online</p>
                    </div>
                  </div>
                </div>

                <div className="relative flex items-center gap-1 z-20">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleFullscreen}
                    className="text-muted-foreground hover:text-foreground hover:bg-black/5 dark:hover:bg-white/10 rounded-full transition-colors"
                  >
                    {isFullscreen ? 'Exit' : 'Full'}
                  </Button>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsOpen(false)}
                    className="text-muted-foreground hover:text-foreground hover:bg-black/5 dark:hover:bg-white/10 rounded-full transition-colors"
                  >
                    ✕
                  </Button>
                </div>
              </div>

              {/* Retention notice */}
              {(() => {
                const s = settings as any;
                return s && typeof s.ai_chat_history_retention_days === 'number' ? (
                  <div className="px-6 pb-2 text-[10px] sm:text-xs text-muted-foreground text-center opacity-60">
                    🕒
                    {t('aiAssistant.chatHistoryRetentionNotice', { days: s.ai_chat_history_retention_days })}
                  </div>
                ) : null;
              })()}

              {/* Messages Area */}
              <ScrollArea ref={scrollAreaRef} className="flex-1 px-4 sm:px-6 relative z-20">
                <div className="flex flex-col space-y-6 pb-4 pt-2">
                  {/* Sentinel element for Intersection Observer to detect when user scrolls to top */}
                  <div ref={sentinelRef} className="h-1" />
                  {isLoadingMore && (
                    <div className="flex justify-center py-4">
                      <Loader className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                  )}
                  {messages.map((msg) => {
                    // Check if message is "rich" (not user, and usually object or long text)
                    const isRichContent = msg.sender === 'ai' && typeof msg.text !== 'string';

                    return (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex flex-col w-full",
                          msg.sender === 'user' ? "items-end" : "items-start"
                        )}
                      >
                        <div
                          className={cn(
                            "flex w-full",
                            msg.sender === 'user' ? "justify-end max-w-[85%] sm:max-w-[75%]" :
                              isRichContent ? "justify-start w-full max-w-full" : "justify-start max-w-[90%] sm:max-w-[85%]"
                          )}
                        >
                          <div className={cn(
                            "relative px-5 py-3.5 shadow-sm text-sm leading-6",
                            msg.sender === 'user'
                              ? "bg-[#2b5876] text-white rounded-2xl rounded-tr-sm"
                              : isRichContent ? "w-full p-0 bg-transparent shadow-none" : "text-foreground rounded-2xl rounded-tl-sm w-full bg-white/50 dark:bg-black/20"
                          )}>
                            {msg.sender === 'user' ? (
                              msg.text
                            ) : (
                              typeof msg.text === 'string' ? (
                                <EnhancedAIResponse text={msg.text} />
                              ) : (
                                msg.text
                              )
                            )}
                          </div>
                        </div>
                        {msg.timestamp && (
                          <div className={cn(
                            "text-[10px] text-muted-foreground/60 mt-1 px-2",
                            msg.sender === 'user' ? "text-right" : "text-left"
                          )}>
                            {formatMessageTime(msg.timestamp, (settings as any)?.timezone)}
                          </div>
                        )}
                      </div>
                    )
                  })}
                  <div ref={messagesEndRef} />
                </div>
              </ScrollArea>

              {/* Input Area */}
              <div className="p-4 sm:p-6 bg-gradient-to-t from-white via-white/80 to-transparent dark:from-gray-950 dark:via-gray-950/80 pt-10 z-30">
                <div className="flex gap-2 mb-4 overflow-x-auto pb-2 scrollbar-hide mask-fade-right">
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full bg-white/50 dark:bg-black/20 backdrop-blur border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 text-xs shadow-sm hover:shadow-md transition-all whitespace-nowrap"
                    onClick={() => handleQuickAction(t('aiAssistant.analyzePatterns'))}
                  >
                    <BarChart3 className="mr-1.5 h-3.5 w-3.5" />
                    {t('aiAssistant.analyzePatterns')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full bg-white/50 dark:bg-black/20 backdrop-blur border-pink-200 dark:border-pink-800 text-pink-600 dark:text-pink-400 text-xs shadow-sm hover:shadow-md transition-all whitespace-nowrap"
                    onClick={() => handleQuickAction(t('aiAssistant.suggestActions'))}
                  >
                    <Target className="mr-1.5 h-3.5 w-3.5" />
                    {t('aiAssistant.suggestActions')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full bg-white/50 dark:bg-black/20 backdrop-blur border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 text-xs shadow-sm hover:shadow-md transition-all whitespace-nowrap"
                    onClick={() => handleQuickAction(t('aiAssistant.paymentCharts'))}
                  >
                    📈
                    {t('aiAssistant.paymentCharts')}
                  </Button>
                </div>

                <div className="relative flex items-center gap-2 bg-white/60 dark:bg-gray-900/50 backdrop-blur-xl border border-gray-200/50 dark:border-gray-700/50 p-2 pl-4 rounded-full shadow-[0_8px_30px_rgb(0,0,0,0.04)] focus-within:shadow-[0_8px_30px_rgb(0,0,0,0.08)] focus-within:border-gray-300 dark:focus-within:border-gray-600 transition-all duration-300">
                  <Input
                    placeholder={t('aiAssistant.inputPlaceholder')}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        handleSendMessage();
                      }
                    }}
                    className="border-0 bg-transparent shadow-none focus-visible:ring-0 px-0 text-base placeholder:text-muted-foreground/60 h-auto py-2.5"
                  />
                  <Button
                    className={cn(
                      "rounded-full w-10 h-10 shrink-0 shadow-md transition-all duration-200 flex items-center justify-center p-0",
                      input.trim()
                        ? "bg-[#2b5876] hover:bg-[#2b5876]/90 text-white translate-x-0 opacity-100"
                        : "bg-gray-200 dark:bg-gray-800 text-gray-400 cursor-not-allowed"
                    )}
                    onClick={() => handleSendMessage()}
                    disabled={!input.trim()}
                  >
                    {isGenerating ? <Loader className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4 ml-0.5" />}
                  </Button>
                </div>
                <div className="text-[10px] text-center text-muted-foreground/40 mt-3">
                  AI can make mistakes. Please check important information.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

export default AIAssistant;
