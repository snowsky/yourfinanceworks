import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { 
  HelpCircle, 
  Play, 
  BookOpen, 
  Video, 
  MessageCircle, 
  Search,
  FileText,
  Users,
  Settings,
  CreditCard,
  Mail
} from 'lucide-react';
import { useOnboarding } from './OnboardingProvider';
import { useTranslation } from 'react-i18next';
import { HELP_ARTICLES_CONTENT } from './HelpArticlesData';
import { ChevronLeft } from 'lucide-react';

export function HelpCenter() {
  const { startTour, tours } = useOnboarding();
  const [searchQuery, setSearchQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('tours');
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null);
  const { t } = useTranslation();

  const helpArticles = [
    {
      id: 'financial-health',
      title: 'Financial Health Fundamentals',
      description: 'Master the core concepts of comprehensive finance management',
      category: 'Foundation',
      icon: BookOpen,
      content: 'This guide explores how to leverage our integrated tools to maintain a healthy financial ecosystem...'
    },
    {
      id: 'revenue-optimization',
      title: 'Revenue Cycle Optimization',
      description: 'Streamline your accounts receivable and collection process',
      category: 'Revenue',
      icon: CreditCard,
      content: 'Learn how to manage the end-to-end revenue cycle, from document generation to final reconciliation...'
    },
    {
      id: 'expense-intelligence',
      title: 'Expense & Outbound Intelligence',
      description: 'Control costs and optimize your business expenditure',
      category: 'Expenditure',
      icon: FileText,
      content: 'Discover how to track, categorize, and analyze expenses to improve your bottom line...'
    },
    {
      id: 'reconciliation-mastery',
      title: 'Banking & Reconciliation',
      description: 'Ensure 100% accounting accuracy with automated tools',
      category: 'Banking',
      icon: Settings,
      content: 'Master the art of automated bank reconciliation and transaction matching...'
    },
    {
      id: 'governance-workflows',
      title: 'Governance & Approvals',
      description: 'Establish robust internal controls and workflows',
      category: 'Compliance',
      icon: Users,
      content: 'Configure multi-level approval hierarchies to ensure spending compliance across your team...'
    },
    {
      id: 'growth-analytics',
      title: 'Strategic Growth Analytics',
      description: 'Turn your financial data into actionable business intelligence',
      category: 'Insights',
      icon: FileText,
      content: 'Leverage our advanced reporting engine to identify growth opportunities and trends...'
    }
  ];

  const filteredArticles = helpArticles.filter(article =>
    article.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    article.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    article.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedArticle = helpArticles.find(a => a.id === selectedArticleId);

  // Simple Markdown Renderer (similar to AIAssistant.tsx)
  const MarkdownRenderer = ({ content }: { content: string }) => {
    if (!content) return null;
    const sections = content.split('\n');
    return (
      <div className="space-y-3 text-[0.95rem] leading-relaxed">
        {sections.map((line, idx) => {
          const isHeader = line.startsWith('#');
          const isBullet = line.trim().startsWith('* ') || line.trim().startsWith('- ') || line.trim().startsWith('• ');
          
          const processInlineBold = (text: string) => {
            const parts = text.split(/(\*\*.*?\*\*)/g);
            return parts.map((part, i) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i} className="font-bold text-primary">{part.slice(2, -2)}</strong>;
              }
              return part;
            });
          };

          if (isBullet) {
            const bulletContent = line.replace(/^[\*\-\•]\s*/, '');
            return (
              <div key={idx} className="flex items-start text-foreground/90 ml-3">
                <span className="mr-2 mt-2 h-1.5 w-1.5 rounded-full bg-primary/40 shrink-0"></span>
                <span>{processInlineBold(bulletContent)}</span>
              </div>
            );
          }

          if (isHeader) {
            const level = line.match(/^#+/)?.[0].length || 1;
            const headerContent = line.replace(/^#+\s+/, '');
            const sizes = ['', 'text-2xl', 'text-xl', 'text-lg', 'text-base'];
            return (
              <div key={idx} className={cn("font-extrabold text-primary pt-4 pb-1", sizes[level] || 'text-base')}>
                {headerContent}
              </div>
            );
          }

          if (!line.trim()) return <div key={idx} className="h-1"></div>;
          if (line.trim() === '---') return <div key={idx} className="my-6 border-t border-border/50"></div>;

          return (
            <div key={idx} className="whitespace-pre-wrap text-muted-foreground font-medium">
              {processInlineBold(line)}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="hover:bg-primary/5 hover:text-primary transition-colors">
          <HelpCircle className="h-4 w-4 mr-2" />
          {t('helpCenter.help')}
        </Button>
      </DialogTrigger>
      
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden z-[1100] p-0 border-none shadow-3xl" onInteractOutside={(e) => e.preventDefault()}>
        <div className="bg-primary/5 border-b border-primary/10 p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3 text-2xl font-bold tracking-tight text-primary">
              <div className="p-2 bg-primary rounded-xl shadow-lg shadow-primary/20">
                <HelpCircle className="h-6 w-6 text-white" />
              </div>
              {t('helpCenter.title')}
            </DialogTitle>
          </DialogHeader>
        </div>
        
        <div className="p-6 h-[70vh] flex flex-col overflow-hidden relative">
          {selectedArticle ? (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="mb-4 flex items-center justify-between">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => {
                    setSelectedArticleId(null);
                    setActiveTab('articles');
                  }}
                  className="hover:bg-primary/5 -ml-2 font-bold transition-all"
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  {t('common.back', 'Back')}
                </Button>
                <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 font-bold">
                  {selectedArticle.category}
                </Badge>
              </div>
              <ScrollArea className="flex-1 -mr-2 pr-4 scrollbar-none">
                <div className="pb-8">
                  <MarkdownRenderer content={HELP_ARTICLES_CONTENT[selectedArticle.id] || selectedArticle.content} />
                </div>
              </ScrollArea>
            </div>
          ) : (
            <Tabs 
              value={activeTab} 
              onValueChange={setActiveTab}
              className="flex-1 flex flex-col overflow-hidden"
            >
            <TabsList className="grid w-full grid-cols-3 mb-8 bg-muted/50 p-1.5 h-12 rounded-xl">
              <TabsTrigger value="tours" className="rounded-lg font-bold data-[state=active]:shadow-md transition-all">{t('helpCenter.tours')}</TabsTrigger>
              <TabsTrigger value="articles" className="rounded-lg font-bold data-[state=active]:shadow-md transition-all">{t('helpCenter.documentation')}</TabsTrigger>
              <TabsTrigger value="support" className="rounded-lg font-bold data-[state=active]:shadow-md transition-all">{t('helpCenter.support')}</TabsTrigger>
            </TabsList>
            
            <TabsContent value="tours" className="flex-1 overflow-y-auto pr-2 space-y-4 -mr-2 scrollbar-none">
              <div className="grid gap-4">
                {tours.map((tour) => (
                  <Card key={tour.id} className="group overflow-hidden border-border/50 hover:border-primary/30 transition-all duration-300 hover:shadow-xl hover:shadow-primary/5">
                    <CardHeader className="pb-3 bg-muted/30 group-hover:bg-primary/5 transition-colors">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg font-bold">{tour.name}</CardTitle>
                        <Badge variant="outline" className="bg-background text-primary border-primary/20 font-bold px-2.5 py-0.5">
                          {tour.steps.length} {t('helpCenter.steps')}
                        </Badge>
                      </div>
                    </CardHeader>
                    
                    <CardContent className="pt-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <p className="text-sm text-muted-foreground font-medium">
                            {t('helpCenter.interactive_walkthrough')}
                          </p>
                          <p className="text-[10px] text-muted-foreground/60 font-bold uppercase tracking-widest">
                            Estimated: {Math.ceil(tour.steps.length * 0.5)} MINS
                          </p>
                        </div>
                        
                        <Button
                          onClick={() => {
                            setOpen(false);
                            startTour(tour.id);
                          }}
                          size="sm"
                          className="shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all hover:-translate-y-0.5"
                        >
                          <Play className="h-3.5 w-3.5 mr-1.5 fill-current" />
                          {t('helpCenter.startTour')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
            
            <TabsContent value="articles" className="flex-1 overflow-y-auto pr-2 -mr-2 space-y-6 scrollbar-none">
              <div className="relative group">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground transition-colors group-focus-within:text-primary" />
                <Input
                  placeholder={t('helpCenter.searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 h-12 rounded-xl border-border/50 bg-muted/30 focus-visible:ring-primary/20 focus-visible:border-primary/30 transition-all"
                />
              </div>
              
              <div className="grid md:grid-cols-2 gap-4">
                {filteredArticles.map((article) => (
                  <Card 
                    key={article.id} 
                    onClick={() => setSelectedArticleId(article.id)}
                    className="group hover:border-primary/20 transition-all duration-300 cursor-pointer overflow-hidden hover:shadow-lg hover:shadow-primary/5 border-border/50"
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start gap-4">
                        <div className="p-3 bg-primary/5 rounded-2xl group-hover:bg-primary/10 transition-colors">
                          <article.icon className="h-5 w-5 text-primary" />
                        </div>
                        
                        <div className="flex-1 space-y-1.5">
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-sm tracking-tight">{article.title}</h3>
                          </div>
                          <p className="text-xs text-muted-foreground leading-relaxed font-medium">
                            {article.description}
                          </p>
                          <div className="pt-1">
                            <Badge variant="secondary" className="text-[9px] font-bold uppercase tracking-wider h-5 px-1.5 py-0">
                              {article.category}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
            
            <TabsContent value="support" className="flex-1 overflow-y-auto pr-2 -mr-2 space-y-6 scrollbar-none">
              <div className="grid md:grid-cols-2 gap-6">
                <Card className="border-primary/10 bg-gradient-to-br from-background to-primary/5 shadow-xl shadow-primary/5 overflow-hidden border-none ring-1 ring-primary/10">
                  <CardHeader className="pb-4">
                    <CardTitle className="flex items-center gap-3 text-xl font-extrabold text-primary">
                      <div className="p-2 bg-primary/10 rounded-xl">
                        <MessageCircle className="h-5 w-5" />
                      </div>
                      Priority Support
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <p className="text-sm text-muted-foreground leading-relaxed font-medium">
                      Need specialized assistance? Our financial platform specialists are ready to help you optimize your operations.
                    </p>
                    
                    <div className="space-y-3">
                      <Button variant="default" className="w-full justify-start h-11 px-4 text-xs font-bold rounded-xl shadow-lg shadow-primary/20 transition-all hover:-translate-y-0.5">
                        <Mail className="h-4 w-4 mr-3" />
                        {t('helpCenter.email_support')}
                      </Button>
                      
                      <Button variant="outline" className="w-full justify-start h-11 px-4 text-xs font-bold rounded-xl border-border hover:bg-muted transition-all">
                        <Video className="h-4 w-4 mr-3" />
                        {t('helpCenter.schedule_demo')}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
                
                <Card className="border-border/50 bg-muted/10 rounded-2xl shadow-none">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-bold uppercase tracking-widest text-muted-foreground">Expert Highlights</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-3 pt-2">
                      {[
                        { tip: t('helpCenter.tip_gamification'), icon: <Settings className="h-3.5 w-3.5" /> },
                        { tip: t('helpCenter.tip_ai'), icon: <Settings className="h-3.5 w-3.5" /> },
                        { tip: t('helpCenter.tip_templates'), icon: <FileText className="h-3.5 w-3.5" /> },
                        { tip: t('helpCenter.tip_reminders'), icon: <Mail className="h-3.5 w-3.5" /> },
                        { tip: t('helpCenter.tip_backups'), icon: <Users className="h-3.5 w-3.5" /> }
                      ].map((item, i) => (
                        <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-background transition-colors border border-transparent hover:border-border/50">
                          <div className="text-primary/60">{item.icon}</div>
                          <span className="text-xs font-medium text-foreground/80">{item.tip}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}