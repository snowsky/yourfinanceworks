import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import * as Dialog from '@radix-ui/react-dialog';
import { Badge } from '@/components/ui/badge';
import { MessageCircle, Send, Sparkles, X, ArrowDown, CheckCircle, AlertCircle, BarChart3, Lightbulb, Target, Loader, Wrench, Maximize2, Minimize2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import PaymentCharts from './PaymentCharts';
import { useTranslation } from 'react-i18next';
import { usePageContext } from '@/contexts/PageContext';
import { promptImprovementApi, type PromptImprovementJob } from '@/lib/api/settings';
import { onboardingAssistantApi, onboardingAiSummary } from '@/lib/api/onboarding';
import { isOnboardingIntent } from '@/components/onboarding/onboardingShortcut';
import { ConfirmActionCard } from '@/components/onboarding/ConfirmActionCard';

// Debug toggle for AI Assistant logs (set VITE_DEBUG_AI_ASSISTANT=true to enable)
const DEBUG_AI_ASSISTANT = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_DEBUG_AI_ASSISTANT === 'true');

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string | React.ReactNode;
  timestamp?: string;
  pending?: boolean;
  failed?: boolean;
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
        <h3 className="text-lg font-bold text-primary mb-3 flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          {t('aiAssistant.invoicePatternAnalysis')}
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className="bg-white/80 dark:bg-black/30 backdrop-blur-sm p-3 rounded-xl shadow-sm border border-border/50">
            <h4 className="font-semibold text-foreground mb-2">{t('aiAssistant.summary')}</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.totalInvoices')}</span>
                <span className="font-medium text-foreground">{data.total_invoices}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.paidInvoices')}</span>
                <span className="font-medium text-success">{data.paid_invoices}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.partiallyPaid')}</span>
                <span className="font-medium text-warning">{data.partially_paid_invoices || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.unpaidInvoices')}</span>
                <span className="font-medium text-destructive">{data.unpaid_invoices}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.overdueInvoices')}</span>
                <span className="font-medium text-destructive">{data.overdue_invoices}</span>
              </div>
            </div>
          </div>

          <div className="bg-white/80 dark:bg-black/30 backdrop-blur-sm p-3 rounded-xl shadow-sm border border-border/50">
            <h4 className="font-semibold text-foreground mb-2">{t('aiAssistant.revenue')}</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.totalRevenue')}</span>
                <span className="font-medium text-success">{formatRevenueByCurrency(data.total_revenue_by_currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('aiAssistant.outstanding')}</span>
                <span className="font-medium text-warning">{formatRevenueByCurrency(data.outstanding_revenue_by_currency)}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-r from-emerald-50 to-blue-50 dark:from-emerald-900/10 dark:to-blue-900/10 p-3 rounded-xl border border-emerald-200/50 dark:border-emerald-800/30">
          <h4 className="font-semibold text-success mb-2 flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            Recommendations
          </h4>
          <ul className="space-y-2 text-sm">
            {data.recommendations.map((rec: string, index: number) => (
              <li key={index} className="flex items-start text-success">
                <span className="text-success mr-2 mt-0.5">•</span>
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
                  <h4 className="font-semibold text-foreground mb-1">{action.action}</h4>
                  <p className="text-sm text-muted-foreground">{action.description}</p>
                </div>
                <div className="ml-3">
                  <Badge variant="outline" className={`${action.priority === 'high' ? 'bg-destructive/10 text-destructive border-destructive/30' :
                    action.priority === 'medium' ? 'bg-warning/10 text-warning border-warning/30' :
                      'bg-success/10 text-success border-success/30'
                    }`}>
                    {action.priority}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/10 dark:to-purple-900/10 p-3 rounded-xl border border-blue-200/50 dark:border-blue-800/30">
          <h4 className="font-semibold text-primary mb-2 flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Quick Summary
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div className="bg-white/60 dark:bg-black/20 p-2 rounded-lg text-center backdrop-blur-sm">
              <div className="text-2xl font-bold text-destructive">{data.overdue_count}</div>
              <div className="text-xs text-muted-foreground">{t('aiAssistant.overdueInvoices')}</div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 p-2 rounded-lg text-center backdrop-blur-sm">
              <div className="text-2xl font-bold text-warning">{data.clients_with_balance}</div>
              <div className="text-xs text-muted-foreground">{t('aiAssistant.clientsWithBalance')}</div>
            </div>
            <div className="bg-white/60 dark:bg-black/20 p-2 rounded-lg text-center backdrop-blur-sm">
              <div className="text-2xl font-bold text-primary">{data.recent_invoices_count}</div>
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
              return <strong key={i} className="font-bold text-foreground">{part.slice(2, -2)}</strong>;
            }
            return part;
          });
        };

        if (isBullet) {
          const bulletContent = line.replace(/^[\*\-\•]\s*/, '');
          return (
            <div key={idx} className="flex items-start text-foreground/90 ml-2">
              <span className="mr-2 mt-1.5 h-1.5 w-1.5 rounded-full bg-primary/50 shrink-0"></span>
              <span>{processInlineBold(bulletContent)}</span>
            </div>
          );
        }

        if (isHeader) {
          const headerContent = line.replace(/^###\s+/, '').replace(/^\*\*/, '').replace(/\*\*$/, '');
          return (
            <div key={idx} className="font-bold text-lg text-foreground mt-2 mb-1">
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
  <div className="min-w-0 rounded-2xl rounded-tl-sm border border-border/70 bg-card p-4 text-sm leading-7 shadow-sm sm:p-5">
    {children}
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

// Prompt Improvement Progress Card
const PromptImprovementProgress = ({ job }: { job: PromptImprovementJob }) => {
  const isRunning = job.status === 'pending' || job.status === 'running';
  const isSucceeded = job.status === 'succeeded';
  const isExhausted = job.status === 'exhausted';
  const isFailed = job.status === 'failed';

  return (
    <div className="w-full rounded-2xl border overflow-hidden">
      {/* Header */}
      <div className={cn(
        "flex items-center gap-3 px-4 py-3",
        isSucceeded ? "bg-success/10 border-b border-success/30" :
        isExhausted ? "bg-warning/10 border-b border-warning/30" :
        isFailed ? "bg-destructive/10 border-b border-destructive/30" :
        "bg-primary/10 border-b border-primary/30"
      )}>
        {isRunning && <Loader className="h-4 w-4 animate-spin text-primary shrink-0" />}
        {isSucceeded && <CheckCircle className="h-4 w-4 text-success shrink-0" />}
        {isExhausted && <AlertCircle className="h-4 w-4 text-warning shrink-0" />}
        {isFailed && <AlertCircle className="h-4 w-4 text-destructive shrink-0" />}
        <div className="flex-1 min-w-0">
          <p className={cn(
            "text-sm font-semibold",
            isSucceeded ? "text-success" :
            isExhausted ? "text-warning" :
            isFailed ? "text-destructive" :
            "text-primary"
          )}>
            {isRunning && (job.prompt_name
              ? `Improving prompt: ${job.prompt_name}`
              : 'Analyzing issue...')}
            {isSucceeded && `Prompt improved successfully`}
            {isExhausted && 'Could not auto-fix — manual edit needed'}
            {isFailed && 'Improvement failed'}
          </p>
          {isRunning && (
            <p className="text-xs text-primary/70">
              Iteration {job.current_iteration} / {job.max_iterations}
            </p>
          )}
        </div>
      </div>

      {/* Result summary */}
      {job.result_summary && (
        <div className="px-4 py-3 text-sm text-foreground bg-white/50 dark:bg-black/20">
          {job.result_summary}
        </div>
      )}

      {/* Error */}
      {job.error_message && (
        <div className="px-4 py-3 text-sm text-destructive bg-destructive/10">
          {job.error_message}
        </div>
      )}

      {/* Iteration log */}
      {job.iteration_log && job.iteration_log.length > 0 && (
        <div className="px-4 py-3 space-y-2 bg-white/30 dark:bg-black/10">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Iterations</p>
          {job.iteration_log.map((entry) => (
            <div key={entry.iteration} className="flex items-start gap-2 text-xs">
              <span className={cn(
                "mt-0.5 shrink-0 font-bold",
                entry.evaluation === 'pass' ? "text-success" : "text-destructive"
              )}>
                {entry.evaluation === 'pass' ? '✓' : '✗'}
              </span>
              <span className="text-muted-foreground">
                <span className="font-medium text-foreground">#{entry.iteration}</span> — {entry.reason}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Link to prompt management on exhaustion */}
      {isExhausted && (
        <div className="px-4 py-3 border-t border-warning/30 bg-warning/10">
          <a
            href="/settings?tab=prompts"
            className="text-xs text-warning underline hover:no-underline"
          >
            Open Prompt Management to edit manually →
          </a>
        </div>
      )}
    </div>
  );
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

  return <StyledAIResponse><MarkdownRenderer content={text} /></StyledAIResponse>;
};

const AIAssistant = React.forwardRef<HTMLDivElement>((_props, ref) => {
  // Check authentication and user role first
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [isAdminUser, setIsAdminUser] = useState(false);
  const [authInitialized, setAuthInitialized] = useState(false);

  // Check authentication and user role
  // Note: token is no longer stored in localStorage (httpOnly cookie); check user data only
  useEffect(() => {
    const checkAuth = () => {
      const userStr = localStorage.getItem('user');
      const authStatus = !!userStr;

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

    // Listen for auth-changed events (dispatched by logout())
    const handleAuthChanged = () => {
      const userStr = localStorage.getItem('user');
      if (!userStr) {
        setIsAuthenticated(false);
        setUser(null);
        setIsAdminUser(false);
      } else {
        checkAuth();
      }
    };

    window.addEventListener('auth-changed', handleAuthChanged);

    // Check auth every 1 second as a fallback for immediate logout detection
    const authInterval = setInterval(() => {
      const userStr = localStorage.getItem('user');

      // If user data is missing, hide the assistant
      if (!userStr) {
        if (isAuthenticated) { // Only update if state changes
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
      window.removeEventListener('auth-changed', handleAuthChanged);
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
const AuthenticatedAIAssistant = React.forwardRef<HTMLDivElement, { user: any }>((_props, ref) => {
  const { t } = useTranslation();
  const { pageContext } = usePageContext();

  const [isOpen, setIsOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [messages, setMessages] = useState<Message[]>(
    [{ id: 1, sender: 'ai', text: <EnhancedAIResponse text={t('aiAssistant.welcomeMessage')} /> }]
  );
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const followLatest = useRef(true);
  const [showJump, setShowJump] = useState(false);
  const [input, setInput] = useState('');
  const [hasUnreadMessages, setHasUnreadMessages] = useState(() => {
    // Check localStorage for persisted unread state, default to true only on first visit
    const stored = localStorage.getItem('ai-assistant-unread');
    return stored === null ? true : stored === 'true';
  });
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const historyLoading = useRef(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [justLoadedHistory, setJustLoadedHistory] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const nextMessageId = useRef(-1);
  const isGenerating = messages.some(message => message.pending);
  useEffect(() => {
    if (isOpen && historyLoaded) composerRef.current?.focus();
  }, [isOpen, historyLoaded]);
  const pollingTimers = useRef(new Set<ReturnType<typeof setInterval>>());
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const timers = pollingTimers.current;
    return () => {
      mounted.current = false;
      timers.forEach(timer => clearInterval(timer));
      timers.clear();
    };
  }, []);

  // Bind each asynchronous response to its own placeholder.
  const updateMessage = useCallback((id: number, content: React.ReactNode | string, failed = false) => {
    if (!mounted.current) return;
    setMessages((prev) => {
      const updated = prev.map(message => message.id === id ? {
        ...message,
        pending: false,
        failed,
        text: typeof content === 'string' ? <EnhancedAIResponse text={content} /> : content,
        timestamp: new Date().toISOString()
      } : message);
      if (!isOpen) {
        setHasUnreadMessages(true);
        localStorage.setItem('ai-assistant-unread', 'true');
      }
      return updated;
    });

  }, [isOpen]);

  // Auto-scroll to bottom when messages change (but not when loading history)
  const scrollToBottom = useCallback(() => {
    // Use setTimeout to ensure DOM has updated
    setTimeout(() => {
      if (!followLatest.current) return;
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, 100);
  }, []);

  useEffect(() => {
    // Only scroll to bottom on initial load or when new messages are added (not when loading history)
    // We can detect new messages by checking if the last message is newer than what we had before
    if (messages.length > 0) {
      const isNewMessage = !isLoadingMore && !justLoadedHistory;

      if (isInitialLoad || (isNewMessage && followLatest.current)) {
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
  const { data: settings, isLoading: settingsLoading, error: settingsError } = useQuery({
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
  const { data: aiConfigs } = useQuery({
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
    if (isOpen && !historyLoaded && !historyLoading.current && !settingsLoading && settings && (settings as any).enable_ai_assistant) {
      historyLoading.current = true;
      (async () => {
        try {
          // Load the last 20 messages (offset 0 = most recent)
          const history = await api.get('/ai/chat/history?limit=20&offset=0') as any[];
          if (!mounted.current) return;
          if (Array.isArray(history) && history.length > 0) {
            const loadedMessages = history.map((msg: any) => ({
              id: msg.id,
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
              const scrollArea = scrollAreaRef.current;
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

              const scrollArea = scrollAreaRef.current;
              if (scrollArea) {
                scrollArea.scrollTop = scrollArea.scrollHeight;
              }
            }, 200);
          }
        } catch (e) {
          if (!mounted.current) return;
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

            const scrollArea = scrollAreaRef.current;
            if (scrollArea) {
              scrollArea.scrollTop = scrollArea.scrollHeight;
            }
          }, 200);
        } finally {
          historyLoading.current = false;
        }
      })();
    }
  }, [isOpen, historyLoaded, settingsLoading, settings, t]);

  useEffect(() => {
    if (isOpen) {
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

        const newMessages = reversedHistory.map((msg: any) => ({
          id: msg.id,
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
      { threshold: 0.1, root: scrollAreaRef.current }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [isOpen, hasMoreHistory, isLoadingMore, historyLoaded, handleLoadMoreHistory]);

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
    const tenantId = localStorage.getItem('selected_tenant_id') || (() => {
      try {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        return user.tenant_id?.toString();
      } catch { return undefined; }
    })();

    const requestUrl = url.startsWith('http') ? url : `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}${url}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(tenantId && { 'X-Tenant-ID': tenantId }),
    };

    const response = await fetch(requestUrl, {
      ...options,
      headers: { ...headers, ...options.headers },
      credentials: 'include',
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
      if (!mounted.current) return;
      await aiApiRequest('/ai/chat/message', {
        method: 'POST',
        body: JSON.stringify({
          message,
          sender
        })
      });
      setHistoryOffset(offset => offset + 1);
    } catch (error) {
      console.error(`Failed to save ${sender} message:`, error);
    }
  };


  const isPromptImprovementIntent = (text: string): boolean =>
    [
      'not being recognized', 'not extracted', 'parsing problem', 'improve prompt',
      'fix prompt', 'extraction issue', 'not reading', 'misread', 'incorrect field',
      'missing field', 'not parsing', 'recognized wrong', 'wrong number',
      'holdings not', 'portfolio not', 'wrong holding', 'incorrect holding',
    ].some((kw) => text.includes(kw));

  const handlePromptImprovementChat = async (message: string, messageId: number) => {
    const updateAiMessage = (content: React.ReactNode | string) => updateMessage(messageId, content);
    const docId = (pageContext as any)?.entity?.id as number | undefined;
    const docType = (pageContext as any)?.entity?.type as 'invoice' | 'expense' | 'bank_statement' | 'portfolio' | undefined;

    let job: PromptImprovementJob;
    try {
      job = await promptImprovementApi.startJob({ message, document_id: docId, document_type: docType });
    } catch (err) {
      updateAiMessage(`Sorry, I couldn't start the prompt improvement job: ${err}`);
      return;
    }

    if (!mounted.current) return;
    // Show initial progress card (stops the thinking indicator)
    updateAiMessage(<PromptImprovementProgress job={job} />);

    let polling = false;
    const pollInterval = setInterval(async () => {
      if (polling || !mounted.current) return;
      polling = true;
      try {
        const updated = await promptImprovementApi.getJob(job.job_id);
        if (!mounted.current) return;
        updateAiMessage(<PromptImprovementProgress job={updated} />);

        if (['succeeded', 'exhausted', 'failed'].includes(updated.status)) {
          clearInterval(pollInterval);
          pollingTimers.current.delete(pollInterval);
          await saveChatMessage(updated.result_summary || updated.error_message || '', 'ai');
        }
      } catch (err) {
        console.error('Prompt improvement poll error:', err);
        clearInterval(pollInterval);
        pollingTimers.current.delete(pollInterval);
      } finally {
        polling = false;
      }
    }, 3000);
    pollingTimers.current.add(pollInterval);
  };

  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (textToSend === '' || !historyLoaded) return;
    followLatest.current = true;
    setShowJump(false);
    const replyId = nextMessageId.current--;
    const updateAiMessage = (content: React.ReactNode | string) => updateMessage(replyId, content);

    const newMessage: Message = {
      id: nextMessageId.current--,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, newMessage]);
    if (!messageText) setInput('');

    // Show typing indicator
    const typingMessage: Message = {
      id: replyId,
      sender: 'ai',
      pending: true,
      text: <EnhancedAIResponse text={t('aiAssistant.thinking')} />,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, typingMessage]);
    await saveChatMessage(textToSend, 'user');

    // Get translated quick action texts (lowercase)
    const analyzePatternsText = t('aiAssistant.analyzePatterns').toLowerCase();
    const suggestActionsText = t('aiAssistant.suggestActions').toLowerCase();
    const paymentChartsText = t('aiAssistant.paymentCharts').toLowerCase();
    const getStartedText = t('aiAssistant.getStarted').toLowerCase();

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
      } else if (isOnboardingIntent(lowerText, getStartedText)) {
        const res = await onboardingAssistantApi.sendOnboardingMessage({ message: textToSend });
        if (res?.data?.type === 'proposed_action') {
          await saveChatMessage(onboardingAiSummary(res.data), 'ai');
          updateAiMessage(
            <ConfirmActionCard
              action={res.data}
              onConfirm={async (a) => {
                const done = await onboardingAssistantApi.sendOnboardingMessage({ message: '', confirmed_action: a });
                if (!done.success) throw new Error(done.error || 'Action failed');
                const doneText = done?.data?.response ?? 'Done.';
                await saveChatMessage(doneText, 'ai');
                updateAiMessage(doneText);
              }}
              onCancel={() => updateAiMessage("No problem — let me know when you're ready.")}
            />,
          );
        } else {
          const aiText = res?.data?.response ?? res?.error ?? 'Let me help you get set up.';
          await saveChatMessage(aiText, 'ai');
          updateAiMessage(aiText);
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
      } else if (isPromptImprovementIntent(lowerText)) {
        await handlePromptImprovementChat(textToSend, replyId);
      } else {
        const response = await aiApiRequest('/ai/chat', {
          method: 'POST',
          body: JSON.stringify({
            message: textToSend,
            config_id: defaultAIConfig?.id || 0,
            page_context: pageContext
          })
        }) as any;
        if (response.success) {
          if (response.data?.type === 'proposed_action') {
            await saveChatMessage(onboardingAiSummary(response.data), 'ai');
            updateAiMessage(<ConfirmActionCard
              action={response.data}
              onConfirm={async (action) => {
                const done = await aiApiRequest('/ai/chat', {
                  method: 'POST', body: JSON.stringify({ message: '', confirmed_action: action }),
                });
                if (!done.success) throw new Error(done.error || 'Action failed');
                const text = done.data.response;
                await saveChatMessage(text, 'ai');
                updateAiMessage(text);
              }}
              onCancel={() => updateAiMessage("No problem — let me know when you’re ready.")}
            />);
          } else {
            const aiResponse = response.data.response || response.data.message || "I'm sorry, I couldn't generate a response.";
            await saveChatMessage(aiResponse, 'ai');
            updateAiMessage(aiResponse);
          }
        } else {
          throw new Error(response.error || 'Failed to get AI response');
        }
      }
    } catch (error) {
      console.error("Error getting AI response:", error);
      const errorMessage = t("aiAssistant.error_message");
      updateMessage(replyId, errorMessage, true);
    }
  };

  const handleQuickAction = (action: string) => {
    // Automatically send the message when quick action is clicked
    handleSendMessage(action);
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const quickActions = [
    { label: t('aiAssistant.analyzePatterns'), icon: BarChart3 },
    { label: t('aiAssistant.suggestActions'), icon: Target },
    { label: t('aiAssistant.paymentCharts'), icon: Lightbulb },
    { label: t('aiAssistant.getStarted'), icon: Sparkles },
    { label: t('aiAssistant.improvePrompt'), message: 'improve prompt - extraction issue', icon: Wrench },
  ];

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button aria-label={t('aiAssistant.openChat')}
          className="fixed bottom-6 right-6 z-50 h-14 w-14 rounded-2xl bg-primary text-primary-foreground shadow-lg transition-transform hover:-translate-y-0.5 motion-reduce:transition-none">
          <MessageCircle className="h-6 w-6" aria-hidden="true" />
          {hasUnreadMessages && <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-background bg-primary" />}
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/45 backdrop-blur-sm" />
        <Dialog.Content ref={ref} onOpenAutoFocus={event => {
          if (historyLoaded) { event.preventDefault(); composerRef.current?.focus(); }
        }} className={cn(
          "fixed inset-0 z-50 flex min-h-0 flex-col overflow-hidden border border-border bg-background shadow-2xl outline-none",
          !isFullscreen && "sm:inset-auto sm:left-1/2 sm:top-1/2 sm:h-[min(820px,90dvh)] sm:w-[calc(100%-3rem)] sm:max-w-3xl sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl"
        )}>
          <header className="flex shrink-0 items-center gap-3 border-b px-4 py-4 sm:px-6">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <Dialog.Title className="text-base font-semibold tracking-tight sm:text-lg">{t('aiAssistant.title')}</Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs leading-5 text-muted-foreground">{t('aiAssistant.subtitle')}</Dialog.Description>
            </div>
            <Button variant="ghost" size="icon" onClick={toggleFullscreen}
              aria-label={isFullscreen ? t('aiAssistant.exitFullscreen') : t('aiAssistant.enterFullscreen')}
              className="hidden shrink-0 sm:inline-flex">
              {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </Button>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label={t('aiAssistant.closeChat')} className="shrink-0">
                <X className="h-5 w-5" aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </header>

          <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground sm:px-6">
            <span role="status" className="flex items-center gap-2">
              {!historyLoaded || isGenerating ? <Loader className="h-3 w-3 animate-spin" aria-hidden="true" /> : <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
              {t(!historyLoaded ? 'aiAssistant.loadingHistory' : isGenerating ? 'aiAssistant.thinking' : 'aiAssistant.ready')}
            </span>
            {typeof (settings as any)?.ai_chat_history_retention_days === 'number' &&
              <span>{t('aiAssistant.chatHistoryRetentionNotice', { days: (settings as any).ai_chat_history_retention_days })}</span>}
          </div>

          <div ref={scrollAreaRef} role="region" aria-label={t('aiAssistant.conversation')}
            onScroll={event => {
              const viewport = event.currentTarget;
              const nearBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 80;
              followLatest.current = nearBottom;
              setShowJump(!nearBottom);
            }} className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-muted/15 px-4 py-6 sm:px-6">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
              <div ref={sentinelRef} className="h-px" />
              {isLoadingMore && <p className="text-center text-xs text-muted-foreground">{t('aiAssistant.loadingHistory')}</p>}
              {!historyLoaded && <div className="space-y-3 animate-pulse" aria-hidden="true">
                <div className="h-16 w-4/5 rounded-2xl bg-muted" /><div className="ml-auto h-12 w-1/2 rounded-2xl bg-muted" />
              </div>}
              {historyLoaded && messages.map(msg => (
                <article key={msg.id} className={cn("min-w-0", msg.sender === 'user' ? 'ml-auto max-w-[90%] sm:max-w-[80%]' : 'w-full')}>
                  <div className={cn("mb-1.5 flex items-center gap-2 text-xs text-muted-foreground", msg.sender === 'user' && 'justify-end')}>
                    <span className="font-medium">{t(msg.sender === 'user' ? 'aiAssistant.you' : 'aiAssistant.assistant')}</span>
                    {msg.timestamp && <time dateTime={msg.timestamp}>{formatMessageTime(msg.timestamp, (settings as any)?.timezone)}</time>}
                  </div>
                  <div role={msg.failed ? 'alert' : undefined} className={cn("min-w-0 break-words [overflow-wrap:anywhere]",
                    msg.sender === 'user' && 'whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-sm leading-6 text-primary-foreground',
                    msg.failed && 'rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-destructive'
                  )}>
                    {msg.pending ? <div className="flex items-center gap-2 rounded-2xl border bg-card px-4 py-4 text-sm text-muted-foreground">
                      <Loader className="h-4 w-4 animate-spin" aria-hidden="true" /><span>{t('aiAssistant.preparingReply')}</span>
                    </div> : msg.sender === 'user' ? msg.text : typeof msg.text === 'string' ? <EnhancedAIResponse text={msg.text} /> : msg.text}
                  </div>
                </article>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
          {showJump && <div className="relative z-10 flex h-0 justify-center">
            <Button size="sm" variant="secondary" className="-translate-y-12 rounded-full border shadow-md" onClick={() => {
              followLatest.current = true; setShowJump(false); scrollToBottom();
            }}><ArrowDown className="mr-2 h-3 w-3" />{t('aiAssistant.latestMessages')}</Button>
          </div>}

          <footer className="shrink-0 border-t bg-background px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 sm:px-6 sm:pt-4">
            <div className="mb-3 flex flex-wrap gap-1.5" aria-label={t('aiAssistant.quickActions')}>
              {quickActions.map(({ label, icon: Icon, message }) => <Button key={label} variant="outline" size="sm"
                className="h-8 rounded-lg px-2.5 text-xs font-normal text-muted-foreground hover:text-foreground"
                disabled={!historyLoaded} onClick={() => handleQuickAction(message || label)}>
                <Icon className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />{label}
              </Button>)}
            </div>
            <div className="rounded-xl border bg-card p-2 shadow-sm focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10">
              <Textarea ref={composerRef} rows={2} disabled={!historyLoaded} aria-label={t('aiAssistant.inputPlaceholder')}
                placeholder={t('aiAssistant.inputPlaceholder')} value={input} onChange={event => setInput(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
                    event.preventDefault(); void handleSendMessage();
                  }
                }} className="max-h-40 min-h-[60px] resize-y border-0 bg-transparent p-2 text-base shadow-none focus-visible:ring-0 sm:text-sm" />
              <div className="flex items-center justify-between gap-2 pl-2">
                <span className="text-[11px] text-muted-foreground">{t('aiAssistant.keyboardHint')}</span>
                <Button size="sm" onClick={() => handleSendMessage()} disabled={!input.trim() || !historyLoaded}
                  aria-label={t('aiAssistant.sendMessage')} className="shrink-0 rounded-lg">
                  <Send className="mr-2 h-3.5 w-3.5" aria-hidden="true" />{t('aiAssistant.sendMessage')}
                </Button>
              </div>
            </div>
            <p className="mt-2 text-center text-[11px] leading-4 text-muted-foreground">{t('aiAssistant.disclaimer')}</p>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
});

export default AIAssistant;
