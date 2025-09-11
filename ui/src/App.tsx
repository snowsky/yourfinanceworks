
import React from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { RoleProtectedRoute } from "./components/auth/RoleProtectedRoute";
import { TenantProtectedRoute } from "./components/auth/TenantProtectedRoute";
import Index from "./pages/Index";
import Login from "./pages/Login";
import OAuthCallback from "./pages/OAuthCallback";
import Signup from "./pages/Signup";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Clients from "./pages/Clients";
import NewClient from "./pages/NewClient";
import EditClient from "./pages/EditClient";
import Invoices from "./pages/Invoices";
import NewInvoice from "./pages/NewInvoice";
import NewInvoiceManual from "./pages/NewInvoiceManual";
import EditInvoice from "./pages/EditInvoice";
import Payments from "./pages/Payments";
import ExpensesNew from "./pages/ExpensesNew";
import ExpensesImport from "./pages/ExpensesImport";
import ExpensesEdit from "./pages/ExpensesEdit";
import Expenses from "./pages/Expenses";
import Statements from "./pages/Statements";
import Settings from "./pages/Settings";
import Users from "./pages/Users";
import SuperAdmin from "./pages/SuperAdmin";
import AIProviderManagement from "./pages/AIProviderManagement";
import NotFound from "./pages/NotFound";
import AIAssistant from "./components/AIAssistant";
import { Toaster } from "sonner";
import AuditLog from "./pages/AuditLog";
import RecycleBin from "./pages/RecycleBin";
import Analytics from "./pages/Analytics";
import Reports from "./pages/Reports";
import AttachmentSearch from "./pages/AttachmentSearch";
import { NotificationBell } from "./components/notifications/NotificationBell";
import { useNotifications } from "./hooks/useNotifications";
import { useExpenseStatusPolling } from "./hooks/useExpenseStatusPolling";
import { getCurrentUser } from "./utils/auth";
import { Favicon } from "./components/ui/favicon";
import { useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";
import { isAdmin } from "@/utils/auth";
import { OnboardingProvider } from "./components/onboarding/OnboardingProvider";
import { TourOverlay } from "./components/onboarding/TourOverlay";


const queryClient = new QueryClient();

const AppContent = () => {
  const { notifications, addNotification, markAsRead, clearAll } = useNotifications();
  const { startPolling } = useExpenseStatusPolling();
  const [bellHidden, setBellHidden] = React.useState(false);
  const isLoggedIn = getCurrentUser() !== null;
  
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
        <OnboardingProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/oauth-callback" element={<OAuthCallback />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/" element={<ProtectedRoute><Index /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Index /></ProtectedRoute>} />
          <Route path="/clients" element={<ProtectedRoute><Clients /></ProtectedRoute>} />
          <Route path="/clients/new" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><NewClient /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/clients/edit/:id" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><EditClient /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/invoices" element={<ProtectedRoute><Invoices /></ProtectedRoute>} />
          <Route path="/invoices/new" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInvoice /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/invoices/new-manual" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInvoiceManual /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/invoices/edit/:id" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><EditInvoice /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/payments" element={<ProtectedRoute><Payments /></ProtectedRoute>} />
          <Route path="/expenses/new" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesNew /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/expenses/import" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesImport /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/expenses/edit/:id" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesEdit /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/expenses" element={<ProtectedRoute><Expenses /></ProtectedRoute>} />
          <Route path="/statements" element={<ProtectedRoute><Statements /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><TenantProtectedRoute requirePrimaryTenant={true}><Settings /></TenantProtectedRoute></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/ai-providers" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><TenantProtectedRoute requirePrimaryTenant={true}><AIProviderManagement /></TenantProtectedRoute></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><Users /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/super-admin" element={<ProtectedRoute><TenantProtectedRoute requireSuperUser={true} requirePrimaryTenant={true}><SuperAdmin /></TenantProtectedRoute></ProtectedRoute>} />
          <Route path="/audit-log" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'superuser']}><AuditLog /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/recycle-bin" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><RecycleBin /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'superuser']}><Analytics /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><Reports /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/attachments" element={<ProtectedRoute><AttachmentSearch /></ProtectedRoute>} />
          <Route path="*" element={<NotFound />} />
          </Routes>
          <TourOverlay />
        </OnboardingProvider>
      </BrowserRouter>
      
      <AIAssistant />
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
      <Toaster position="top-center" richColors />
    </TooltipProvider>
  );
};

const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
};

export default App;
