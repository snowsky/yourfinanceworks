import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Building2, FileText, Percent, Cpu, Bell, Activity, Search,
  Database, User, Lock, Mail, Shield, ExternalLink, ShieldCheck, Terminal, Trophy, Puzzle, Settings2
} from "lucide-react";
import { getCurrentUser } from "@/utils/auth";
import {
  CompanyInfoTab, InvoiceSettingsTab, UserProfileTab, DiscountRulesTab, AIConfigTab,
  NotificationsTab, DataManagementTab, CurrenciesTab, SearchSettingsTab,
  CookieSettingsTab, ExportDestinationsTab, EmailIntegrationSettingsTab,
  APIClientManagementTab, LicenseManagementTab, GamificationTab, PluginsTab
} from "@/components/settings";
import PromptManagement from "./PromptManagement";

const SIDEBAR_TRIGGER = "w-full justify-start px-3 py-2.5 h-auto rounded-lg text-sm font-medium " +
  "data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm " +
  "hover:bg-muted/60 transition-all duration-200 text-muted-foreground whitespace-nowrap";

const Settings = () => {
  const { t } = useTranslation();

  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === 'admin';

  const [activeTab, setActiveTab] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const defaultTab = isAdmin ? 'company' : 'profile';
    return urlParams.get('tab') || defaultTab;
  });

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    if (tab && tab !== activeTab) {
      setActiveTab(tab);
    }
  }, []);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const currentTab = urlParams.get('tab');
    if (activeTab !== currentTab) {
      if (activeTab) {
        urlParams.set('tab', activeTab);
      } else {
        urlParams.delete('tab');
      }
      const newUrl = `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`;
      window.history.replaceState({}, '', newUrl);
    }
  }, [activeTab]);

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Hero Header */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-6">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold tracking-tight">{t('settings.title')}</h1>
            <p className="text-lg text-muted-foreground">{t('settings.description')}</p>
          </div>
          <Settings2 className="w-16 h-16 text-primary/15 flex-shrink-0 hidden sm:block" />
        </div>
      </div>

      {/* Sidebar + Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-col md:flex-row gap-6 items-start">

          {/* Vertical Sidebar */}
          <div className="w-full md:w-[220px] md:flex-shrink-0 md:sticky md:top-6">
            <TabsList className="flex flex-row md:flex-col h-auto w-full bg-muted/20 p-2 rounded-xl border border-border/30 gap-0.5 overflow-x-auto md:overflow-x-visible">

              {/* Personal */}
              <p className="hidden md:block px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 w-full">
                {t('settings.categories.personal', 'Personal')}
              </p>
              <TabsTrigger value="profile" className={SIDEBAR_TRIGGER}>
                <User className="w-4 h-4 mr-2 flex-shrink-0" />
                {t('settings.tabs.profile', 'Profile')}
              </TabsTrigger>
              <TabsTrigger value="cookies" className={SIDEBAR_TRIGGER}>
                <Lock className="w-4 h-4 mr-2 flex-shrink-0" />
                {t('settings.tabs.cookies', 'Privacy')}
              </TabsTrigger>

              {isAdmin && (
                <>
                  {/* Company */}
                  <div className="hidden md:block border-t border-border/30 my-1 w-full" />
                  <p className="hidden md:block px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 w-full">
                    {t('settings.categories.company', 'Company')}
                  </p>
                  <TabsTrigger value="company" className={SIDEBAR_TRIGGER}>
                    <Building2 className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.company', 'Company')}
                  </TabsTrigger>
                  <TabsTrigger value="invoices" className={SIDEBAR_TRIGGER}>
                    <FileText className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.invoices', 'Invoices')}
                  </TabsTrigger>
                  <TabsTrigger value="discount-rules" className={SIDEBAR_TRIGGER}>
                    <Percent className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.discount_rules', 'Discounts')}
                  </TabsTrigger>

                  {/* Features */}
                  <div className="hidden md:block border-t border-border/30 my-1 w-full" />
                  <p className="hidden md:block px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 w-full">
                    {t('settings.categories.features', 'Features')}
                  </p>
                  <TabsTrigger value="ai-config" className={SIDEBAR_TRIGGER}>
                    <Cpu className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.ai_config', 'AI Config')}
                  </TabsTrigger>
                  <TabsTrigger value="gamification" className={SIDEBAR_TRIGGER}>
                    <Trophy className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.gamification', 'Gamification')}
                  </TabsTrigger>
                  <TabsTrigger value="plugins" className={SIDEBAR_TRIGGER}>
                    <Puzzle className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.plugins', 'Plugins')}
                  </TabsTrigger>
                  <TabsTrigger value="search" className={SIDEBAR_TRIGGER}>
                    <Search className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.search', 'Search')}
                  </TabsTrigger>
                  <TabsTrigger value="export" className={SIDEBAR_TRIGGER}>
                    <ExternalLink className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.export_destinations', 'Exports')}
                  </TabsTrigger>

                  {/* Integrations */}
                  <div className="hidden md:block border-t border-border/30 my-1 w-full" />
                  <p className="hidden md:block px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 w-full">
                    {t('settings.categories.integrations', 'Integrations')}
                  </p>
                  <TabsTrigger value="notifications" className={SIDEBAR_TRIGGER}>
                    <Bell className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.email_notifications', 'Notifications')}
                  </TabsTrigger>
                  <TabsTrigger value="currencies" className={SIDEBAR_TRIGGER}>
                    <Activity className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.currencies', 'Currencies')}
                  </TabsTrigger>
                  <TabsTrigger value="api-integrations" className={SIDEBAR_TRIGGER}>
                    <Mail className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.email', 'Email')}
                  </TabsTrigger>
                  <TabsTrigger value="api-clients" className={SIDEBAR_TRIGGER}>
                    <ShieldCheck className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.api_keys', 'API Keys')}
                  </TabsTrigger>

                  {/* System */}
                  <div className="hidden md:block border-t border-border/30 my-1 w-full" />
                  <p className="hidden md:block px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60 w-full">
                    {t('settings.categories.system', 'System')}
                  </p>
                  <TabsTrigger value="prompts" className={SIDEBAR_TRIGGER}>
                    <Terminal className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.prompts', 'Prompts')}
                  </TabsTrigger>
                  <TabsTrigger value="license" className={SIDEBAR_TRIGGER}>
                    <Shield className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.license.tabTitle', 'License')}
                  </TabsTrigger>
                  <TabsTrigger value="data" className={SIDEBAR_TRIGGER}>
                    <Database className="w-4 h-4 mr-2 flex-shrink-0" />
                    {t('settings.tabs.export', 'Data')}
                  </TabsTrigger>
                </>
              )}
            </TabsList>
          </div>

          {/* Content Area */}
          <div className="flex-1 min-w-0">
            <TabsContent value="profile" className="m-0 focus-visible:outline-none">
              <UserProfileTab />
            </TabsContent>

            <TabsContent value="cookies" className="m-0 focus-visible:outline-none">
              <CookieSettingsTab />
            </TabsContent>

            {isAdmin && (
              <>
                <TabsContent value="company" className="m-0 focus-visible:outline-none">
                  <CompanyInfoTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="invoices" className="m-0 focus-visible:outline-none">
                  <InvoiceSettingsTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="discount-rules" className="m-0 focus-visible:outline-none">
                  <DiscountRulesTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="ai-config" className="m-0 focus-visible:outline-none">
                  <AIConfigTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="gamification" className="m-0 focus-visible:outline-none">
                  <GamificationTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="plugins" className="m-0 focus-visible:outline-none">
                  <PluginsTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="notifications" className="m-0 focus-visible:outline-none">
                  <NotificationsTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="currencies" className="m-0 focus-visible:outline-none">
                  <CurrenciesTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="search" className="m-0 focus-visible:outline-none">
                  <SearchSettingsTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="export" className="m-0 focus-visible:outline-none">
                  <ExportDestinationsTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="api-integrations" className="m-0 focus-visible:outline-none">
                  <EmailIntegrationSettingsTab />
                </TabsContent>

                <TabsContent value="api-clients" className="m-0 focus-visible:outline-none">
                  <APIClientManagementTab />
                </TabsContent>

                <TabsContent value="prompts" className="m-0 focus-visible:outline-none">
                  <PromptManagement />
                </TabsContent>

                <TabsContent value="license" className="m-0 focus-visible:outline-none">
                  <LicenseManagementTab />
                </TabsContent>

                <TabsContent value="data" className="m-0 focus-visible:outline-none">
                  <DataManagementTab isAdmin={isAdmin} />
                </TabsContent>
              </>
            )}
          </div>
        </div>
      </Tabs>
    </div>
  );
};

export default Settings;
