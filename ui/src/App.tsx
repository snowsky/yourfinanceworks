
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { RoleProtectedRoute } from "./components/auth/RoleProtectedRoute";
import { TenantProtectedRoute } from "./components/auth/TenantProtectedRoute";
import Index from "./pages/Index";
import Login from "./pages/Login";
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
import ExpensesEdit from "./pages/ExpensesEdit";
import Expenses from "./pages/Expenses";
import Settings from "./pages/Settings";
import Users from "./pages/Users";
import SuperAdmin from "./pages/SuperAdmin";
import NotFound from "./pages/NotFound";
import AIAssistant from "./components/AIAssistant";
import { Toaster } from "sonner";
import AuditLog from "./pages/AuditLog";
import RecycleBin from "./pages/RecycleBin";
import Analytics from "./pages/Analytics";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>

      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
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
          <Route path="/expenses/edit/:id" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><ExpensesEdit /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/expenses" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><Expenses /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><TenantProtectedRoute requirePrimaryTenant={true}><Settings /></TenantProtectedRoute></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><Users /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/super-admin" element={<ProtectedRoute><TenantProtectedRoute requireSuperUser={true} requirePrimaryTenant={true}><SuperAdmin /></TenantProtectedRoute></ProtectedRoute>} />
          <Route path="/audit-log" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'superuser']}><AuditLog /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/recycle-bin" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><RecycleBin /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'superuser']}><Analytics /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <AIAssistant />
      <Toaster position="bottom-center" richColors />
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
