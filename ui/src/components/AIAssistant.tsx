import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Send, Bot } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api, aiApi } from '@/lib/api'; // Import both api and aiApi

interface Message {
  id: number;
  sender: 'user' | 'ai';
  text: string | React.ReactNode;
}

const AIAssistant = React.forwardRef<HTMLDivElement>((props, ref) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>(
    [{ id: 1, sender: 'ai', text: "Hello! I'm your Invoice Assistant. How can I help you today?" }]
  );
  const [input, setInput] = useState('');
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Check if user is authenticated (reactive)
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      const user = localStorage.getItem('user');
      const authStatus = !!(token && user);
      console.log('AI Assistant: Authentication check', { token: !!token, user: !!user, authStatus });
      setIsAuthenticated(authStatus);
    };
    
    checkAuth();
    
    // Check authentication on localStorage changes
    const handleStorageChange = () => {
      checkAuth();
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Fetch user settings to check the enable_ai_assistant flag
  const { data: settings, isLoading: settingsLoading, error: settingsError } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings/'),
    refetchInterval: (query) => {
      // Stop refetching if there's an authentication error
      if (query.state.error && 
          (query.state.error.message.includes('403') || 
           query.state.error.message.includes('Authentication failed'))) {
        console.log('AI Assistant: Stopping refetch due to authentication error');
        return false;
      }
      return 5000; // Refetch every 5 seconds if no auth error
    },
    refetchOnWindowFocus: true, // Refetch when window gains focus
    refetchOnMount: true, // Always refetch on mount
    staleTime: 0, // Consider data immediately stale to ensure fresh data
    enabled: isAuthenticated, // Only run query when authenticated
    retry: (failureCount, error) => {
      // Don't retry on authentication errors
      if (error.message.includes('403') || error.message.includes('Authentication failed')) {
        console.log('AI Assistant: Not retrying due to authentication error');
        return false;
      }
      return failureCount < 3;
    },
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
    enabled: isAuthenticated && !!(settings && (settings as any).enable_ai_assistant), // Only fetch if authenticated and AI assistant is enabled
    retry: (failureCount, error) => {
      // Don't retry on authentication errors
      if (error.message.includes('403') || error.message.includes('Authentication failed')) {
        console.log('AI Assistant: Not retrying AI configs due to authentication error');
        return false;
      }
      return failureCount < 3;
    },
  });

  // Handle authentication errors
  useEffect(() => {
    if (settingsError && (settingsError.message.includes('403') || settingsError.message.includes('Authentication failed'))) {
      console.log('AI Assistant: Authentication error detected, clearing auth state');
      // Clear authentication state to trigger re-authentication
      setIsAuthenticated(false);
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  }, [settingsError]);

  console.log('AI Assistant: Component state', {
    isAuthenticated,
    settings,
    settingsLoading,
    settingsError,
    aiConfigs,
    aiConfigsLoading,
    componentWillRender: isAuthenticated && !settingsLoading
  });

  // Don't render anything if not authenticated
  if (!isAuthenticated) {
    console.log('AI Assistant: Not rendering - not authenticated');
    return null;
  }

  const isAIAssistantEnabled = settings && (settings as any).enable_ai_assistant;
  const defaultAIConfig = aiConfigs && Array.isArray(aiConfigs) ? 
    (aiConfigs as any[]).find((config: any) => config.is_default && config.is_active) : 
    undefined;

  // Enhanced debug logging
  console.log('AI Assistant Debug:', { 
    settings, 
    settingsLoading, 
    settingsError, 
    isAIAssistantEnabled,
    aiConfigs,
    aiConfigsLoading,
    defaultAIConfig,
    shouldRender: !settingsLoading && isAIAssistantEnabled 
  });

  // CRITICAL: Add detailed logging for disabled state
  console.log('AI Assistant Render Decision:', {
    isAuthenticated,
    settingsLoading,
    settingsError: !!settingsError,
    settings: settings,
    isAIAssistantEnabled,
    rawSettingsValue: settings ? (settings as any).enable_ai_assistant : 'no settings',
    willRender: isAuthenticated && !settingsLoading && isAIAssistantEnabled
  });

  // Don't render if loading or AI assistant is disabled
  if (settingsLoading) {
    console.log('AI Assistant: Not rendering because settings are loading');
    return null;
  }

  // If there's an error fetching settings, default to showing the AI assistant
  if (settingsError) {
    console.log('AI Assistant: Error fetching settings, defaulting to show:', settingsError);
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
    const typingMessage: Message = { id: messages.length + 2, sender: 'ai', text: "Thinking..." };
    setMessages((prev) => [...prev, typingMessage]);

    try {
      // Check for specific patterns that should use dedicated endpoints
      const lowerText = textToSend.toLowerCase();
      console.log('AI Assistant: Processing message:', { textToSend, lowerText });
      
      if (lowerText.includes('analyze') && lowerText.includes('pattern')) {
        // Use the analyze-patterns endpoint (MCP-like functionality)
        console.log('AI Assistant: Using analyze-patterns endpoint');
        try {
          const response = await aiApi.analyzePatterns();
          console.log('AI Assistant: Analyze patterns response:', response);
          
          if (response.success) {
            const data = response.data;
            const analysisText = `
**Invoice Pattern Analysis**

📊 **Summary:**
- Total Invoices: ${data.total_invoices}
- Paid Invoices: ${data.paid_invoices}
- Unpaid Invoices: ${data.unpaid_invoices}
- Overdue Invoices: ${data.overdue_invoices}
- Total Revenue: $${data.total_revenue}
- Outstanding Revenue: $${data.outstanding_revenue}

💡 **Recommendations:**
${data.recommendations.map((rec: string) => `- ${rec}`).join('\n')}
            `.trim();
            
            setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: analysisText }]);
          } else {
            throw new Error('Failed to analyze patterns');
          }
        } catch (error) {
          console.error('AI Assistant: Error calling analyze-patterns:', error);
          throw error;
        }
      } else if (lowerText.includes('suggest') && lowerText.includes('action')) {
        // Use the suggest-actions endpoint (MCP-like functionality)
        console.log('AI Assistant: Using suggest-actions endpoint');
        try {
          const response = await aiApi.suggestActions();
          console.log('AI Assistant: Suggest actions response:', response);
          
          if (response.success) {
            const data = response.data;
            const actionsText = `
**Suggested Actions**

🎯 **Recommended Actions:**
${data.suggested_actions.map((action: any) => `- **${action.action}**: ${action.description} (Priority: ${action.priority})`).join('\n')}

📈 **Summary:**
- Overdue Invoices: ${data.overdue_count}
- Clients with Balance: ${data.clients_with_balance}
- Recent Invoices: ${data.recent_invoices_count}
            `.trim();
            
            setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: actionsText }]);
          } else {
            throw new Error('Failed to get suggestions');
          }
        } catch (error) {
          console.error('AI Assistant: Error calling suggest-actions:', error);
          throw error;
        }
      } else {
        // Use the regular chat endpoint
        console.log('AI Assistant: Using chat endpoint');
        
        // Check if we have a default AI configuration
        if (!defaultAIConfig) {
          console.log('AI Assistant: No default AI config found:', { aiConfigs, defaultAIConfig });
          const errorMessage = "No AI configuration found. Please configure an AI provider in Settings > AI Configuration.";
          setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: errorMessage }]);
          return;
        }
        
        const response = await aiApi.chat(textToSend, defaultAIConfig.id);

        if (response.success) {
          const aiResponse = response.data.response || response.data.message || "I'm sorry, I couldn't generate a response.";
          setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: aiResponse }]);
        } else {
          throw new Error('Failed to get AI response');
        }
      }
    } catch (error) {
      console.error("Error getting AI response:", error);
      const errorMessage = "Sorry, I encountered an error. Please try again or check your AI configuration.";
      setMessages((prev) => [...prev.slice(0, -1), { id: prev.length, sender: 'ai', text: errorMessage }]);
    }
  };

  const handleQuickAction = (action: string) => {
    // Automatically send the message when quick action is clicked
    handleSendMessage(action);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <TooltipProvider>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  className="rounded-full w-20 h-20 shadow-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 hover:scale-105 transition-transform duration-200 border-4 border-white/40 backdrop-blur-lg"
                  style={{ boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)' }}
                  onClick={() => setIsOpen(true)}
                >
                  <Bot className="h-10 w-10 text-white drop-shadow-lg" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>AI Assistant</p>
              </TooltipContent>
            </Tooltip>
          </DialogTrigger>
          <DialogContent className="w-full max-w-[600px] h-[80vh] max-h-[800px] flex flex-col p-0 bg-white/70 backdrop-blur-2xl rounded-3xl shadow-2xl border-0 overflow-hidden animate-fade-in">
            <div className="relative bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500 p-6 flex items-center gap-4 rounded-t-3xl shadow-md">
              <div className="bg-white/30 rounded-full p-3 shadow-lg">
                <Bot className="h-10 w-10 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white drop-shadow">Invoice AI Assistant</h2>
                <p className="text-white/80 text-sm mt-1">Ask me anything about your business</p>
              </div>
            </div>
            <ScrollArea ref={scrollAreaRef} className="flex-grow px-6 py-4 overflow-y-auto">
              <div className="flex flex-col space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`px-4 py-3 rounded-2xl max-w-[80%] shadow-md transition-all duration-200 ${msg.sender === 'user' ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white self-end animate-bounce-in-right' : 'bg-white/80 text-gray-900 self-start animate-bounce-in-left border border-gray-200'}`}
                    style={{ wordBreak: 'break-word', whiteSpace: 'pre-line' }}
                  >
                    {msg.text}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>
            <div className="flex space-x-2 px-6 pb-3 pt-2">
              <Button
                variant="outline"
                className="rounded-xl bg-gradient-to-r from-blue-100 to-purple-100 text-blue-700 font-semibold shadow hover:from-blue-200 hover:to-purple-200"
                onClick={() => handleQuickAction('Analyze my invoice patterns')}
              >
                Analyze Patterns
              </Button>
              <Button
                variant="outline"
                className="rounded-xl bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700 font-semibold shadow hover:from-pink-200 hover:to-purple-200"
                onClick={() => handleQuickAction('Suggest actions')}
              >
                Suggest Actions
              </Button>
            </div>
            <div className="flex items-center px-6 pb-6 pt-2 gap-2">
              <Input
                placeholder="Type your message..."
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
          </DialogContent>
        </Dialog>
      </TooltipProvider>
    </div>
  );
});

export default AIAssistant;
