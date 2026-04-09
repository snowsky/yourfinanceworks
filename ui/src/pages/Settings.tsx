import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  Building2, FileText, Percent, Cpu, Bell, Activity, Search,
  Database, User, Lock, Mail, Shield, ExternalLink, ShieldCheck, Terminal, Trophy, Puzzle, Settings2, Palette, CreditCard
} from "lucide-react";
import { getCurrentUser } from "@/utils/auth";
import {
  CompanyInfoTab, InvoiceSettingsTab, UserProfileTab, DiscountRulesTab, AIConfigTab,
  NotificationsTab, DataManagementTab, CurrenciesTab, SearchSettingsTab,
  CookieSettingsTab, ExportDestinationsTab, EmailIntegrationSettingsTab,
  APIClientManagementTab, LicenseManagementTab, GamificationTab, PluginsTab,
  AppearanceTab, PaymentSettingsTab
} from "@/components/settings";
import PromptManagement from "./PromptManagement";

const NavItem = ({ value, icon: Icon, label, activeTab, onClick }: {
  value: string; icon: React.ElementType; label: string; activeTab: string; onClick: (v: string) => void;
}) => (
  <button
    onClick={() => onClick(value)}
    className={cn(
      "w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 text-left",
      activeTab === value
        ? "bg-primary text-primary-foreground shadow-sm"
        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
    )}
  >
    <Icon className="w-4 h-4 flex-shrink-0" />
    <span>{label}</span>
  </button>
);

const Settings = () => {
  const { t } = useTranslation();

  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === 'admin';

  const [activeTab, setActiveTab] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const defaultTab = 'profile';
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
            <nav className="flex flex-col gap-0.5 bg-muted/20 p-2 rounded-xl border border-border/30">

              {/* Personal */}
              <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                {t('settings.categories.personal', 'Personal')}
              </p>
              <NavItem value="profile" icon={User} label={t('settings.tabs.profile', 'Profile')} activeTab={activeTab} onClick={setActiveTab} />
              <NavItem value="appearance" icon={Palette} label={t('settings.tabs.appearance', 'Appearance')} activeTab={activeTab} onClick={setActiveTab} />
              <NavItem value="cookies" icon={Lock} label={t('settings.tabs.cookies', 'Privacy')} activeTab={activeTab} onClick={setActiveTab} />

              {isAdmin && (
                <>
                  {/* Company */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.company', 'Company')}
                  </p>
                  <NavItem value="company" icon={Building2} label={t('settings.tabs.company', 'Company')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="invoices" icon={FileText} label={t('settings.tabs.invoices', 'Invoices')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="discount-rules" icon={Percent} label={t('settings.tabs.discount_rules', 'Discounts')} activeTab={activeTab} onClick={setActiveTab} />

                  {/* Features */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.features', 'Features')}
                  </p>
                  <NavItem value="ai-config" icon={Cpu} label={t('settings.tabs.ai_config', 'AI Config')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="gamification" icon={Trophy} label={t('settings.tabs.gamification', 'Gamification')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="plugins" icon={Puzzle} label={t('settings.tabs.plugins', 'Plugins')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="search" icon={Search} label={t('settings.tabs.search', 'Search')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="export" icon={ExternalLink} label={t('settings.tabs.export_destinations', 'Exports')} activeTab={activeTab} onClick={setActiveTab} />

                  {/* Integrations */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.integrations', 'Integrations')}
                  </p>
                  <NavItem value="notifications" icon={Bell} label={t('settings.tabs.email_notifications', 'Notifications')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="currencies" icon={Activity} label={t('settings.tabs.currencies', 'Currencies')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="payments" icon={CreditCard} label={t('settings.tabs.payments', 'Payments')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="api-integrations" icon={Mail} label={t('settings.tabs.email', 'Email')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="api-clients" icon={ShieldCheck} label={t('settings.tabs.api_keys', 'API Keys')} activeTab={activeTab} onClick={setActiveTab} />

                  {/* System */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.system', 'System')}
                  </p>
                  <NavItem value="prompts" icon={Terminal} label={t('settings.tabs.prompts', 'Prompts')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="license" icon={Shield} label={t('settings.license.tabTitle', 'License')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="data" icon={Database} label={t('settings.tabs.export', 'Data')} activeTab={activeTab} onClick={setActiveTab} />
                </>
              )}
            </nav>
          </div>

          {/* Content Area */}
          <div className="flex-1 min-w-0">
            <TabsContent value="profile" className="m-0 focus-visible:outline-none">
              <UserProfileTab />
            </TabsContent>

            <TabsContent value="appearance" className="m-0 focus-visible:outline-none">
              <AppearanceTab />
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

                <TabsContent value="payments" className="m-0 focus-visible:outline-none">
                  <PaymentSettingsTab />
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
