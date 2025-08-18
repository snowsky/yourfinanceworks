import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
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

export function HelpCenter() {
  const { startTour, tours } = useOnboarding();
  const [searchQuery, setSearchQuery] = useState('');
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();

  const helpArticles = [
    {
      id: 'getting-started',
      title: 'Getting Started Guide',
      description: 'Learn the basics of managing invoices and clients',
      category: 'Basics',
      icon: BookOpen,
      content: 'This comprehensive guide covers everything you need to know to get started with Invoice Manager...'
    },
    {
      id: 'creating-invoices',
      title: 'Creating Your First Invoice',
      description: 'Step-by-step guide to creating professional invoices',
      category: 'Invoices',
      icon: FileText,
      content: 'Learn how to create, customize, and send professional invoices to your clients...'
    },
    {
      id: 'client-management',
      title: 'Managing Clients',
      description: 'Add, edit, and organize your client information',
      category: 'Clients',
      icon: Users,
      content: 'Discover how to effectively manage your client database and relationships...'
    },
    {
      id: 'payment-tracking',
      title: 'Tracking Payments',
      description: 'Monitor and record payments from your clients',
      category: 'Payments',
      icon: CreditCard,
      content: 'Learn how to track payments, mark invoices as paid, and manage overdue accounts...'
    },
    {
      id: 'email-setup',
      title: 'Email Configuration',
      description: 'Set up email delivery for sending invoices',
      category: 'Settings',
      icon: Mail,
      content: 'Configure your email settings to send professional invoices directly to clients...'
    }
  ];

  const filteredArticles = helpArticles.filter(article =>
    article.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    article.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    article.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          <HelpCircle className="h-4 w-4 mr-2" />
          Help
        </Button>
      </DialogTrigger>
      
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden" onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5" />
            {t('helpCenter.title')}
          </DialogTitle>
        </DialogHeader>
        
        <Tabs defaultValue="tours" className="h-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="tours">{t('helpCenter.tours')}</TabsTrigger>
            <TabsTrigger value="articles">{t('helpCenter.documentation')}</TabsTrigger>
            <TabsTrigger value="support">{t('helpCenter.support')}</TabsTrigger>
          </TabsList>
          
          <TabsContent value="tours" className="space-y-4 overflow-y-auto max-h-[60vh]">
            <div className="grid gap-4">
              {tours.map((tour) => (
                <Card key={tour.id} className="hover:shadow-md transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{tour.name}</CardTitle>
                      <Badge variant="secondary">
                        {tour.steps.length} steps
                      </Badge>
                    </div>
                  </CardHeader>
                  
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <p className="text-sm text-muted-foreground">
                          Interactive walkthrough of key features
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Duration: ~{Math.ceil(tour.steps.length * 0.5)} minutes
                        </p>
                      </div>
                      
                      <Button
                        onClick={() => {
                          startTour(tour.id);
                          setOpen(false);
                        }}
                        size="sm"
                      >
                        <Play className="h-4 w-4 mr-1" />
                        {t('helpCenter.startTour')}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
          
          <TabsContent value="articles" className="space-y-4 overflow-y-auto max-h-[60vh]">
            <div className="flex items-center gap-2 mb-4">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('helpCenter.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1"
              />
            </div>
            
            <div className="grid gap-3">
              {filteredArticles.map((article) => (
                <Card key={article.id} className="hover:shadow-md transition-shadow cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-primary/10 rounded-lg">
                        <article.icon className="h-4 w-4 text-primary" />
                      </div>
                      
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-sm">{article.title}</h3>
                          <Badge variant="outline" className="text-xs">
                            {article.category}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {article.description}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
          
          <TabsContent value="support" className="space-y-4 overflow-y-auto max-h-[60vh]">
            <div className="grid gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageCircle className="h-5 w-5" />
                    Contact Support
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Need additional help? Our support team is here to assist you.
                  </p>
                  
                  <div className="space-y-2">
                    <Button variant="outline" className="w-full justify-start">
                      <Mail className="h-4 w-4 mr-2" />
                      Email Support
                    </Button>
                    
                    <Button variant="outline" className="w-full justify-start">
                      <Video className="h-4 w-4 mr-2" />
                      Schedule a Demo
                    </Button>
                  </div>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader>
                  <CardTitle>Quick Tips</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="text-sm space-y-2">
                    <p>• Use keyboard shortcuts: Ctrl+N for new invoice</p>
                    <p>• Save time with invoice templates</p>
                    <p>• Set up automatic payment reminders</p>
                    <p>• Export data regularly for backups</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}