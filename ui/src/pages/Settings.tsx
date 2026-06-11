import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Building2, FileText, Percent, Cpu, Bell, Activity, Search,
  Database, User, Lock, Mail, Shield, ExternalLink, ShieldCheck, Terminal, Trophy, Puzzle, Settings2, Palette, CreditCard, Landmark, Share2
} from "lucide-react";
import { getCurrentUser } from "@/utils/auth";
import { usePermissionChecker } from "@/hooks/usePermissions";
import {
  CompanyInfoTab, InvoiceSettingsTab, UserProfileTab, DiscountRulesTab, AIConfigTab,
  NotificationsTab, DataManagementTab, CurrenciesTab, SearchSettingsTab,
  CookieSettingsTab, ExportDestinationsTab, EmailIntegrationSettingsTab,
  APIClientManagementTab, LicenseManagementTab, GamificationTab, PluginsTab,
  AppearanceTab, PaymentSettingsTab, ExpensesSettingsTab, CashFlowSettingsTab,
  SharingSettingsTab
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
  // Per-component grants can demote a tenant admin below admin on Settings.
  // While the permission request is loading we leave the role-based decision
  // alone so admins don't flash a disabled UI on first paint.
  const permissionChecker = usePermissionChecker();
  const isAdmin =
    currentUser?.role === 'admin' &&
    (permissionChecker.isLoading ||
      permissionChecker.hasPermission('settings', 'admin'));

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

  const activeTabLabelMap: Record<string, string> = {
    profile: t('settings.tabs.profile'),
    appearance: t('settings.tabs.appearance'),
    cookies: t('settings.tabs.cookies'),
    company: t('settings.tabs.company'),
    invoices: t('settings.tabs.invoices'),
    expenses: t('settings.tabs.expenses'),
    cashflow: t('settings.tabs.cashflow'),
    sharing: t('settings.tabs.sharing'),
    'discount-rules': t('settings.tabs.discount_rules'),
    'ai-config': t('settings.tabs.ai_config'),
    gamification: t('settings.tabs.gamification'),
    plugins: t('settings.tabs.plugins'),
    search: t('settings.tabs.search'),
    export: t('settings.tabs.export_destinations'),
    notifications: t('settings.tabs.email_notifications'),
    currencies: t('settings.tabs.currencies'),
    payments: t('settings.tabs.payments'),
    'api-integrations': t('settings.tabs.email'),
    'api-clients': t('settings.tabs.api_keys'),
    prompts: t('settings.tabs.prompts'),
    license: t('settings.license.tabTitle'),
    data: t('settings.tabs.export'),
  };

  const activeTabLabel = activeTabLabelMap[activeTab] || t('settings.title');
  const activeTabDescriptionMap: Record<string, string> = {
    expenses: t(
      'settings.expenses.description',
      'Manage mobile expense settings, expense digest delivery, policy thresholds, validation rules, defaults, and approval notifications.'
    ),
  };
  const activeTabDescription = activeTabDescriptionMap[activeTab] || t('settings.description');

  return (
    <div className="h-full space-y-8 fade-in dashboard-highlight-mode dashboard-shell pb-12">
      {/* Hero Header */}
      <div className="dashboard-highlight-block dashboard-highlight-block-primary dashboard-hero bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 md:p-7 backdrop-blur-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="space-y-2 flex-1">
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">{t('settings.title')}</h1>
            <p className="text-muted-foreground text-sm md:text-base">{activeTabDescription}</p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/25">
                <Settings2 className="w-3 h-3 mr-1" />
                {activeTabLabel}
              </Badge>
              <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">
                <User className="w-3 h-3 mr-1" />
                {isAdmin ? t('common.admin') : t('common.user')}
              </Badge>
            </div>
          </div>
          <Settings2 className="w-16 h-16 text-primary/15 flex-shrink-0 hidden sm:block" />
        </div>
      </div>

      {/* Sidebar + Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-col md:flex-row gap-6 items-start">

          {/* Vertical Sidebar */}
          <div className="w-full md:w-[220px] md:flex-shrink-0 md:sticky md:top-6">
            <nav className="dashboard-highlight-block dashboard-highlight-block-primary flex flex-col gap-0.5 bg-muted/20 p-2 rounded-xl border border-border/40 shadow-sm">

              {/* Personal */}
              <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                {t('settings.categories.personal')}
              </p>
              <NavItem value="profile" icon={User} label={t('settings.tabs.profile')} activeTab={activeTab} onClick={setActiveTab} />
              <NavItem value="appearance" icon={Palette} label={t('settings.tabs.appearance')} activeTab={activeTab} onClick={setActiveTab} />
              <NavItem value="cookies" icon={Lock} label={t('settings.tabs.cookies')} activeTab={activeTab} onClick={setActiveTab} />

              {isAdmin && (
                <>
                  {/* Company */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.company')}
                  </p>
                  <NavItem value="company" icon={Building2} label={t('settings.tabs.company')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="invoices" icon={FileText} label={t('settings.tabs.invoices')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="expenses" icon={FileText} label={t('settings.tabs.expenses')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="cashflow" icon={Landmark} label={t('settings.tabs.cashflow')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="sharing" icon={Share2} label={t('settings.tabs.sharing')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="discount-rules" icon={Percent} label={t('settings.tabs.discount_rules')} activeTab={activeTab} onClick={setActiveTab} />

                  {/* Features */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.features')}
                  </p>
                  <NavItem value="ai-config" icon={Cpu} label={t('settings.tabs.ai_config')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="gamification" icon={Trophy} label={t('settings.tabs.gamification')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="plugins" icon={Puzzle} label={t('settings.tabs.plugins')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="search" icon={Search} label={t('settings.tabs.search')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="export" icon={ExternalLink} label={t('settings.tabs.export_destinations')} activeTab={activeTab} onClick={setActiveTab} />

                  {/* Integrations */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.integrations')}
                  </p>
                  <NavItem value="notifications" icon={Bell} label={t('settings.tabs.email_notifications')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="currencies" icon={Activity} label={t('settings.tabs.currencies')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="payments" icon={CreditCard} label={t('settings.tabs.payments')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="api-integrations" icon={Mail} label={t('settings.tabs.email')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="api-clients" icon={ShieldCheck} label={t('settings.tabs.api_keys')} activeTab={activeTab} onClick={setActiveTab} />

                  {/* System */}
                  <div className="border-t border-border/30 my-1" />
                  <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                    {t('settings.categories.system')}
                  </p>
                  <NavItem value="prompts" icon={Terminal} label={t('settings.tabs.prompts')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="license" icon={Shield} label={t('settings.license.tabTitle')} activeTab={activeTab} onClick={setActiveTab} />
                  <NavItem value="data" icon={Database} label={t('settings.tabs.export')} activeTab={activeTab} onClick={setActiveTab} />
                </>
              )}
            </nav>
          </div>

          {/* Content Area */}
          <div className="flex-1 min-w-0 dashboard-highlight-block dashboard-highlight-block-primary rounded-2xl border border-border/40 bg-card/70 p-4 md:p-5 shadow-sm">
            <div className="pb-4 mb-4 border-b border-border/40">
              <h2 className="text-lg md:text-xl font-semibold tracking-tight">{activeTabLabel}</h2>
              <p className="text-sm text-muted-foreground">{activeTabDescription}</p>
            </div>
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

                <TabsContent value="expenses" className="m-0 focus-visible:outline-none">
                  <ExpensesSettingsTab isAdmin={isAdmin} />
                </TabsContent>

                <TabsContent value="cashflow" className="m-0 focus-visible:outline-none">
                  <CashFlowSettingsTab />
                </TabsContent>

                <TabsContent value="sharing" className="m-0 focus-visible:outline-none">
                  <SharingSettingsTab isAdmin={isAdmin} />
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
