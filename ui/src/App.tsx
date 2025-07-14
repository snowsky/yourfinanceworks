
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { RoleProtectedRoute } from "./components/auth/RoleProtectedRoute";
import Index from "./pages/Index";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Clients from "./pages/Clients";
import NewClient from "./pages/NewClient";
import EditClient from "./pages/EditClient";
import Invoices from "./pages/Invoices";
import NewInvoice from "./pages/NewInvoice";
import EditInvoice from "./pages/EditInvoice";
import Payments from "./pages/Payments";
import Settings from "./pages/Settings";
import Users from "./pages/Users";
import NotFound from "./pages/NotFound";
import AIAssistant from "./components/AIAssistant";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>

      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/" element={<ProtectedRoute><Index /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Index /></ProtectedRoute>} />
          <Route path="/clients" element={<ProtectedRoute><Clients /></ProtectedRoute>} />
          <Route path="/clients/new" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><NewClient /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/clients/edit/:id" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><EditClient /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/invoices" element={<ProtectedRoute><Invoices /></ProtectedRoute>} />
          <Route path="/invoices/new" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><NewInvoice /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/invoices/edit/:id" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin', 'user']}><EditInvoice /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/payments" element={<ProtectedRoute><Payments /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><Settings /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute><RoleProtectedRoute allowedRoles={['admin']}><Users /></RoleProtectedRoute></ProtectedRoute>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <AIAssistant />
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
