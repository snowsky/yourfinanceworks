import React, { useState, useEffect } from 'react';
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

  // Fetch user settings to check the enable_ai_assistant flag
  const { data: settings, isLoading: settingsLoading, error: settingsError } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings/'),
    refetchInterval: 5000, // Refetch every 5 seconds to catch settings changes
  });

  // Fetch AI configurations
  const { data: aiConfigs, isLoading: aiConfigsLoading } = useQuery({
    queryKey: ['ai-configs'],
    queryFn: () => api.get('/ai-config/'),
    enabled: !!settings?.enable_ai_assistant, // Only fetch if AI assistant is enabled
  });

  const isAIAssistantEnabled = settings?.enable_ai_assistant;
  const defaultAIConfig = aiConfigs?.find((config: any) => config.is_default && config.is_active);

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
    console.log('AI Assistant: Not rendering because AI assistant is disabled');
    return null;
  }

  console.log('AI Assistant: Rendering component');

  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (textToSend === '') return;

    const newMessage: Message = { id: messages.length + 1, sender: 'user', text: textToSend };
    setMessages((prev) => [...prev, newMessage]);
    if (!messageText) setInput('');

    // Show typing indicator
    const typingMessage = { id: messages.length + 2, sender: 'ai', text: "Thinking..." };
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
    <div className="fixed bottom-4 right-4 z-50">
      <TooltipProvider>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  className="rounded-full w-16 h-16 shadow-lg bg-blue-600 hover:bg-blue-700"
                  onClick={() => setIsOpen(true)}
                >
                  <Bot className="h-6 w-6" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>AI Assistant</p>
              </TooltipContent>
            </Tooltip>
          </DialogTrigger>
        <DialogContent className="w-[400px] h-[600px] flex flex-col">
          <DialogHeader>
            <DialogTitle>Invoice AI Assistant</DialogTitle>
          </DialogHeader>
          <ScrollArea className="flex-grow p-4 border rounded-md mb-4">
            <div className="flex flex-col space-y-2">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`p-2 rounded-lg max-w-[80%] ${msg.sender === 'user' ? 'bg-blue-500 text-white self-end' : 'bg-gray-200 self-start'}`}
                >
                  {msg.text}
                </div>
              ))}
            </div>
          </ScrollArea>
          <div className="flex space-x-2 mb-4">
            <Button onClick={() => handleQuickAction("Analyze my invoice patterns")}>Analyze Patterns</Button>
            <Button onClick={() => handleQuickAction("Suggest actions")}>Suggest Actions</Button>
          </div>
          <div className="flex">
            <Input
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleSendMessage();
                }
              }}
              className="flex-grow mr-2"
            />
            <Button onClick={() => handleSendMessage()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </DialogContent>
        </Dialog>
      </TooltipProvider>
    </div>
  );
});

export default AIAssistant;
