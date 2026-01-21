import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Building2, FileText, Percent, Cpu, Bell, Activity, Search,
  Database, User, Lock, Mail, Shield, ExternalLink, ShieldCheck, Terminal, Trophy
} from "lucide-react";
import { getCurrentUser } from "@/utils/auth";
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";
import {
  CompanyInfoTab, InvoiceSettingsTab, UserProfileTab, DiscountRulesTab, AIConfigTab,
  NotificationsTab, DataManagementTab, CurrenciesTab, SearchSettingsTab,
  CookieSettingsTab, ExportDestinationsTab, EmailIntegrationSettingsTab,
  APIClientManagementTab, LicenseManagementTab, GamificationTab
} from "@/components/settings";
import PromptManagement from "./PromptManagement";

const Settings = () => {
  const { t } = useTranslation();

  // Get current user and check if admin
  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === 'admin';

  // Get tab from URL parameters, default to 'company' or 'profile'
  const [activeTab, setActiveTab] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const defaultTab = isAdmin ? 'company' : 'profile';
    return urlParams.get('tab') || defaultTab;
  });

  // Update active tab when URL changes
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    if (tab && tab !== activeTab) {
      setActiveTab(tab);
    }
  }, []);

  // Update URL when active tab changes
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
      <PageHeader
        title={t('settings.title')}
        description={t('settings.description')}
      />

      <ContentSection>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="mb-8 flex flex-wrap h-auto bg-muted/20 p-1 gap-1 justify-start rounded-lg border-none">
            <TabsTrigger
              value="profile"
              className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
            >
              <User className="w-4 h-4 mr-2" />
              {t('settings.tabs.profile', t('settings.profile.user_profile'))}
            </TabsTrigger>

            {isAdmin && (
              <>
                <TabsTrigger
                  value="company"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Building2 className="w-4 h-4 mr-2" />
                  {t('settings.tabs.company')}
                </TabsTrigger>
                <TabsTrigger
                  value="invoices"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  {t('settings.tabs.invoices')}
                </TabsTrigger>
                <TabsTrigger
                  value="discount-rules"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Percent className="w-4 h-4 mr-2" />
                  {t('settings.tabs.discount_rules')}
                </TabsTrigger>
                <TabsTrigger
                  value="ai-config"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Cpu className="w-4 h-4 mr-2" />
                  {t('settings.tabs.ai_config')}
                </TabsTrigger>
                <TabsTrigger
                  value="gamification"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Trophy className="w-4 h-4 mr-2" />
                  {t('settings.tabs.gamification')}
                </TabsTrigger>
                <TabsTrigger
                  value="notifications"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Bell className="w-4 h-4 mr-2" />
                  {t('settings.tabs.email_notifications')}
                </TabsTrigger>
                <TabsTrigger
                  value="currencies"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Activity className="w-4 h-4 mr-2" />
                  {t('settings.tabs.currencies')}
                </TabsTrigger>
                <TabsTrigger
                  value="search"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Search className="w-4 h-4 mr-2" />
                  {t('settings.tabs.search')}
                </TabsTrigger>
                <TabsTrigger
                  value="export"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <ExternalLink className="w-4 h-4 mr-2" />
                  {t('settings.tabs.export_destinations')}
                </TabsTrigger>
                <TabsTrigger
                  value="api-integrations"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Mail className="w-4 h-4 mr-2" />
                  {t('settings.tabs.email')}
                </TabsTrigger>
                <TabsTrigger
                  value="api-clients"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <ShieldCheck className="w-4 h-4 mr-2" />
                  {t('settings.tabs.api_keys')}
                </TabsTrigger>
                <TabsTrigger
                  value="prompts"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Terminal className="w-4 h-4 mr-2" />
                  {t('settings.tabs.prompts')}
                </TabsTrigger>
                <TabsTrigger
                  value="license"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Shield className="w-4 h-4 mr-2" />
                  {t('settings.license.tabTitle')}
                </TabsTrigger>
                <TabsTrigger
                  value="data"
                  className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
                >
                  <Database className="w-4 h-4 mr-2" />
                  {t('settings.tabs.export')}
                </TabsTrigger>
              </>
            )}
            <TabsTrigger
              value="cookies"
              className="px-4 py-2 h-auto data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm rounded-md hover:bg-muted transition-all"
            >
              <Lock className="w-4 h-4 mr-2" />
              {t('settings.tabs.cookies')}
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 min-w-0">
            <TabsContent value="profile" className="m-0 focus-visible:outline-none">
              <UserProfileTab />
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

            <TabsContent value="cookies" className="m-0 focus-visible:outline-none">
              <CookieSettingsTab />
            </TabsContent>
          </div>
        </Tabs>
      </ContentSection>
    </div>
  );
};

export default Settings;
