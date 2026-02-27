/**
 * Copyright (c) 2026 YourFinanceWORKS
 * This file is part of the UI of YourFinanceWORKS.
 * Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
 * See LICENSE-AGPLv3.txt for details.
 */

import React from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { RoleProtectedRoute } from "./components/auth/RoleProtectedRoute";
import { TenantProtectedRoute } from "./components/auth/TenantProtectedRoute";
import { Toaster } from "sonner";
import { useNotifications } from "./hooks/useNotifications";
import { useExpenseStatusPolling } from "./hooks/useExpenseStatusPolling";
import { useJoinRequestPolling } from "./hooks/useJoinRequestPolling";
import { getCurrentUser } from "./utils/auth";
import { useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";
import { isAdmin } from "@/utils/auth";
import { LoadingSpinner } from "@/components/ui/loading-spinner";

// Lazy load only page components for code splitting
const Index = React.lazy(() => import("./pages/Index"));
const Login = React.lazy(() => import("./pages/Login"));
const OAuthCallback = React.lazy(() => import("./pages/OAuthCallback"));
const Signup = React.lazy(() => import("./pages/Signup"));
const ForgotPassword = React.lazy(() => import("./pages/ForgotPassword"));
const ResetPassword = React.lazy(() => import("./pages/ResetPassword"));
const Clients = React.lazy(() => import("./pages/Clients"));
const NewClient = React.lazy(() => import("./pages/NewClient"));
const EditClient = React.lazy(() => import("./pages/EditClient"));
const Invoices = React.lazy(() => import("./pages/Invoices"));
const NewInvoice = React.lazy(() => import("./pages/NewInvoice"));
const NewInvoiceManual = React.lazy(() => import("./pages/NewInvoiceManual"));
const EditInvoice = React.lazy(() => import("./pages/EditInvoice"));
const ViewInvoice = React.lazy(() => import("./pages/ViewInvoice"));
const Payments = React.lazy(() => import("./pages/Payments"));
const ExpensesNew = React.lazy(() => import("./pages/ExpensesNew"));
const ExpensesImport = React.lazy(() => import("./pages/ExpensesImport"));
const ExpensesEdit = React.lazy(() => import("./pages/ExpensesEdit"));
const ExpensesView = React.lazy(() => import("./pages/ExpensesView"));
const Expenses = React.lazy(() => import("./pages/Expenses"));
const Statements = React.lazy(() => import("./pages/Statements"));
const Settings = React.lazy(() => import("./pages/Settings"));
const Users = React.lazy(() => import("./pages/Users"));
const SuperAdmin = React.lazy(() => import("./pages/SuperAdmin"));

// Investment Management Components
const InvestmentDashboard = React.lazy(() => import("./pages/investments/InvestmentDashboard"));
const CreatePortfolio = React.lazy(() => import("./pages/investments/CreatePortfolio"));
const PortfolioDetail = React.lazy(() => import("./pages/investments/PortfolioDetail"));
const PortfolioPerformance = React.lazy(() => import("./pages/investments/PortfolioPerformance"));
const InvestmentAnalytics = React.lazy(() => import("./pages/investments/InvestmentAnalytics"));
const TaxExport = React.lazy(() => import("./pages/investments/TaxExport"));
const RebalancingTool = React.lazy(() => import("./pages/investments/RebalancingTool"));
const CrossPortfolioAnalysis = React.lazy(() => import("./pages/investments/CrossPortfolioAnalysis"));
const NotFound = React.lazy(() => import("./pages/NotFound"));
const AIAssistant = React.lazy(() => import("./components/AIAssistant"));
const AuditLog = React.lazy(() => import("./pages/AuditLog"));
const RecycleBin = React.lazy(() => import("./pages/RecycleBin"));
const ExpenseRecycleBin = React.lazy(() => import("./pages/ExpenseRecycleBin"));
const StatementRecycleBin = React.lazy(() => import("./pages/StatementRecycleBin"));
const Analytics = React.lazy(() => import("./pages/Analytics"));
const Reports = React.lazy(() => import("./pages/Reports"));
const ReportDetail = React.lazy(() => import("./pages/ReportDetail"));
const AttachmentSearch = React.lazy(() => import("./pages/AttachmentSearch"));
const ActivityPage = React.lazy(() => import("./pages/ActivityPage").then(module => ({ default: module.ActivityPage })));
const NotificationBell = React.lazy(() => import("./components/notifications/NotificationBell").then(module => ({ default: module.NotificationBell })));
const Favicon = React.lazy(() => import("./components/ui/favicon").then(module => ({ default: module.Favicon })));
const OnboardingProvider = React.lazy(() => import("./components/onboarding/OnboardingProvider").then(module => ({ default: module.OnboardingProvider })));
const TourOverlay = React.lazy(() => import("./components/onboarding/TourOverlay").then(module => ({ default: module.TourOverlay })));
const SearchProvider = React.lazy(() => import("./components/search/SearchProvider").then(module => ({ default: module.SearchProvider })));
const SearchDialog = React.lazy(() => import("./components/search/SearchDialog").then(module => ({ default: module.SearchDialog })));
const FeatureProvider = React.lazy(() => import("./contexts/FeatureContext").then(module => ({ default: module.FeatureProvider })));
const PluginProvider = React.lazy(() => import("./contexts/PluginContext").then(module => ({ default: module.PluginProvider })));
const PluginStorageNotifications = React.lazy(() => import("./components/notifications/PluginStorageNotifications").then(module => ({ default: module.PluginStorageNotifications })));
const PluginRouteErrorBoundary = React.lazy(() => import("./components/plugins/PluginRouteErrorBoundary").then(module => ({ default: module.PluginRouteErrorBoundary })));
const PluginRouteGuard = React.lazy(() => import("./components/plugins/PluginRouteGuard").then(module => ({ default: module.PluginRouteGuard })));
const ApprovalDashboard = React.lazy(() => import("./components/approvals/ApprovalDashboard").then(module => ({ default: module.ApprovalDashboard })));
const AppLayout = React.lazy(() => import("./components/layout/AppLayout").then(module => ({ default: module.AppLayout })));
const AuthenticatedLayout = React.lazy(() => import("./components/layout/AuthenticatedLayout").then(module => ({ default: module.AuthenticatedLayout })));
const Inventory = React.lazy(() => import("./pages/Inventory"));
const NewInventoryItem = React.lazy(() => import("./pages/NewInventoryItem"));
const EditInventoryItem = React.lazy(() => import("./pages/EditInventoryItem"));
const InventoryItemDetail = React.lazy(() => import("./pages/InventoryItemDetail"));
const NewInventoryInvoice = React.lazy(() => import("./pages/NewInventoryInvoice"));
const ApprovalReportsPage = React.lazy(() => import("./pages/ApprovalReportsPage"));
const Reminders = React.lazy(() => import("./pages/Reminders"));
const OrganizationJoinRequests = React.lazy(() => import("./pages/OrganizationJoinRequests"));
const PromptManagement = React.lazy(() => import("./pages/PromptManagement"));

const queryClient = new QueryClient();

// Simple redirect component for expense IDs
const ExpenseRedirect = () => {
  const { id } = useParams();
  return <Navigate to={`/expenses/view/${id}`} replace />;
};

// Simple redirect component for invoice IDs
const InvoiceRedirect = () => {
  const { id } = useParams();
  return <Navigate to={`/invoices/view/${id}`} replace />;
};

// Simple redirect component for client IDs
const ClientRedirect = () => {
  const { id } = useParams();
  return <Navigate to={`/clients/edit/${id}`} replace />;
};

const AppContent = () => {
  const { notifications, addNotification, markAsRead, clearAll } = useNotifications();
  const { startPolling } = useExpenseStatusPolling();
  const [bellHidden, setBellHidden] = React.useState(false);
  const isLoggedIn = getCurrentUser() !== null;
  const currentUser = getCurrentUser();
  const userIsAdmin = currentUser?.role === 'admin';

  // Poll for new join requests if user is admin
  useJoinRequestPolling(userIsAdmin, addNotification);

  // Get company branding for favicon
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    enabled: isLoggedIn && isAdmin(),
    retry: false,
  });

  // Make notification functions available globally
  React.useEffect(() => {
    (window as any).addAINotification = addNotification;
    (window as any).startExpensePolling = startPolling;
  }, [addNotification, startPolling]);

  // Show bell again when new notifications arrive
  React.useEffect(() => {
    if (notifications.length > 0 && notifications.some(n => !n.read)) {
      setBellHidden(false);
    }
  }, [notifications]);

  return (
    <TooltipProvider>
      <Favicon
        logoUrl={settings?.company_info?.logo}
        companyName={settings?.company_info?.name}
      />

      <BrowserRouter>
        <FeatureProvider>
          <PluginProvider>
            <PluginStorageNotifications />
            <SearchProvider>
            <OnboardingProvider>
              <React.Suspense fallback={<LoadingSpinner fullScreen />}>
                <Routes>
                  <Route path="/login" element={<Login />} />
                  <Route path="/oauth-callback" element={<OAuthCallback />} />
                  <Route path="/signup" element={<Signup />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                  <Route element={<ProtectedRoute><AuthenticatedLayout /></ProtectedRoute>}>
                    <Route path="/" element={<Index />} />
                    <Route path="/dashboard" element={<Index />} />
                    <Route path="/clients" element={<Clients />} />
                    <Route path="/clients/:id" element={<ClientRedirect />} />
                    <Route path="/clients/new" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><NewClient /></RoleProtectedRoute>} />
                    <Route path="/clients/edit/:id" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><EditClient /></RoleProtectedRoute>} />
                    <Route path="/invoices" element={<Invoices />} />
                    <Route path="/invoices/new" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInvoice /></RoleProtectedRoute>} />
                    <Route path="/invoices/new-manual" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInvoiceManual /></RoleProtectedRoute>} />
                    <Route path="/invoices/view/:id" element={<ViewInvoice />} />
                    <Route path="/invoices/edit/:id" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><EditInvoice /></RoleProtectedRoute>} />
                    <Route path="/invoices/:id" element={<InvoiceRedirect />} />
                    <Route path="/expenses/new" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesNew /></RoleProtectedRoute>} />
                    <Route path="/expenses/import" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesImport /></RoleProtectedRoute>} />
                    <Route path="/expenses/view/:id" element={<ExpensesView />} />
                    <Route path="/expenses/edit/:id" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesEdit /></RoleProtectedRoute>} />
                    <Route path="/expenses/:id" element={<ExpenseRedirect />} />
                    <Route path="/expenses" element={<Expenses />} />
                    <Route path="/payments" element={<Payments />} />
                    <Route path="/reminders" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><Reminders /></RoleProtectedRoute>} />
                    <Route path="/approvals" element={<ApprovalDashboard />} />
                    <Route path="/approvals/reports" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><ApprovalReportsPage /></RoleProtectedRoute>} />
                    <Route path="/statements" element={<Statements />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/users" element={<RoleProtectedRoute allowedRoles={['admin']}><Users /></RoleProtectedRoute>} />
                    <Route path="/organization-join-requests" element={<RoleProtectedRoute allowedRoles={['admin']}><OrganizationJoinRequests /></RoleProtectedRoute>} />
                    <Route path="/super-admin" element={<TenantProtectedRoute requireSuperUser={true} requirePrimaryTenant={true}><SuperAdmin /></TenantProtectedRoute>} />
                    <Route path="/audit-log" element={<RoleProtectedRoute allowedRoles={['admin', 'superuser']}><AuditLog /></RoleProtectedRoute>} />
                    <Route path="/recycle-bin" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><RecycleBin /></RoleProtectedRoute>} />
                    <Route path="/analytics" element={<RoleProtectedRoute allowedRoles={['admin', 'superuser']}><Analytics /></RoleProtectedRoute>} />

                    {/* Investment Management Routes */}
                    <Route path="/investments" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments"
                        >
                          <InvestmentDashboard />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/investments/portfolio/new" element={
                      <RoleProtectedRoute allowedRoles={['admin', 'user']}>
                        <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                          <PluginRouteErrorBoundary
                            pluginId="investments"
                            pluginName="Investment Management"
                            routePath="/investments/portfolio/new"
                          >
                            <CreatePortfolio />
                          </PluginRouteErrorBoundary>
                        </PluginRouteGuard>
                      </RoleProtectedRoute>
                    } />
                    <Route path="/investments/portfolio/:id" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments/portfolio/:id"
                        >
                          <PortfolioDetail />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/investments/portfolio/:id/performance" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments/portfolio/:id/performance"
                        >
                          <PortfolioPerformance />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/investments/portfolio/:id/rebalance" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments/portfolio/:id/rebalance"
                        >
                          <RebalancingTool />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/investments/analytics" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments/analytics"
                        >
                          <InvestmentAnalytics />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/investments/tax-export" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments/tax-export"
                        >
                          <TaxExport />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/investments/cross-portfolio" element={
                      <PluginRouteGuard pluginId="investments" pluginName="Investment Management">
                        <PluginRouteErrorBoundary
                          pluginId="investments"
                          pluginName="Investment Management"
                          routePath="/investments/cross-portfolio"
                        >
                          <CrossPortfolioAnalysis />
                        </PluginRouteErrorBoundary>
                      </PluginRouteGuard>
                    } />
                    <Route path="/reports" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><Reports /></RoleProtectedRoute>} />
                    <Route path="/reports/:reportType" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><ReportDetail /></RoleProtectedRoute>} />
                    <Route path="/attachments" element={<AttachmentSearch />} />
                    <Route path="/activity" element={<ActivityPage />} />
                    <Route path="/inventory" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><Inventory /></RoleProtectedRoute>} />
                    <Route path="/inventory/new" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInventoryItem /></RoleProtectedRoute>} />
                    <Route path="/inventory/view/:id" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><InventoryItemDetail /></RoleProtectedRoute>} />
                    <Route path="/inventory/edit/:id" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><EditInventoryItem /></RoleProtectedRoute>} />
                    <Route path="/inventory/new-inventory" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInventoryInvoice /></RoleProtectedRoute>} />
                    <Route path="/prompts" element={<RoleProtectedRoute allowedRoles={['admin']}><PromptManagement /></RoleProtectedRoute>} />
                    <Route path="/expenses/recycle-bin" element={<ExpenseRecycleBin />} />
                    <Route path="/statements/recycle-bin" element={<StatementRecycleBin />} />
                  </Route>
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </React.Suspense>
              {isLoggedIn && !bellHidden && (
                <NotificationBell
                  notifications={notifications}
                  onMarkAsRead={markAsRead}
                  onClearAll={clearAll}
                  onHide={() => setBellHidden(true)}
                />
              )}
              {isLoggedIn && bellHidden && notifications.some(n => !n.read) && (
                <div
                  className="fixed top-4 right-4 z-50 cursor-pointer"
                  onClick={() => setBellHidden(false)}
                  title="Show AI notifications"
                >
                  <div className="w-3 h-3 bg-blue-600 rounded-full animate-pulse"></div>
                </div>
              )}
              <TourOverlay />
            </OnboardingProvider>
            <SearchDialog />
          </SearchProvider>
          </PluginProvider>
        </FeatureProvider>
      </BrowserRouter>

      <AIAssistant />
      <Toaster position="top-center" richColors />
    </TooltipProvider>
  );
};

const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="invoice-app-theme">
        <AppContent />
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
