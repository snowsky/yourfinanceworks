
import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { UserProfile } from "./UserProfile";
import { 
  BarChart, 
  ChevronLeft, 
  DollarSign, 
  FileText, 
  LogOut,
  Settings, 
  Users 
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(!isMobile);
  const [tenantName, setTenantName] = useState('InvoiceApp');

  // Get tenant name from user data
  React.useEffect(() => {
    const userData = localStorage.getItem('user');
    if (userData) {
      try {
        const user = JSON.parse(userData);
        // You can get tenant name from user data or make an API call
        // For now, we'll use a default or fetch it from the tenant API
        fetchTenantName();
      } catch (error) {
        console.error('Error parsing user data:', error);
      }
    }
  }, []);

  const fetchTenantName = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return;

      const response = await fetch(`${API_BASE_URL}/tenants/me`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const tenant = await response.json();
        setTenantName(tenant.name);
      }
    } catch (error) {
      console.error('Error fetching tenant name:', error);
    }
  };

  const handleLogout = () => {
    // Clear authentication data
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    
    // Clear React Query cache to prevent 403 errors
    queryClient.clear();
    
    // Redirect to login page
    navigate('/login');
  };

  const menuItems = [
    { 
      path: '/', 
      label: 'Dashboard', 
      icon: <BarChart className="w-5 h-5" /> 
    },
    { 
      path: '/clients', 
      label: 'Clients', 
      icon: <Users className="w-5 h-5" /> 
    },
    { 
      path: '/invoices', 
      label: 'Invoices', 
      icon: <FileText className="w-5 h-5" /> 
    },
    { 
      path: '/payments', 
      label: 'Payments', 
      icon: <DollarSign className="w-5 h-5" /> 
    },
    { 
      path: '/settings', 
      label: 'Settings', 
      icon: <Settings className="w-5 h-5" /> 
    }
  ];

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <>
      <Sidebar>
        <SidebarHeader className="py-6 px-2 border-b border-sidebar-border">
          <div className="flex flex-col items-center text-center">
            <span className="text-xl font-bold text-white">InvoiceApp</span>
            <span className="text-sm text-gray-300 mt-1 truncate max-w-full px-2">
              {tenantName}
            </span>
          </div>
        </SidebarHeader>
        <SidebarContent className="pt-6">
          <SidebarMenu>
            {menuItems.map((item) => (
              <SidebarMenuItem key={item.path}>
                <SidebarMenuButton asChild 
                  className={isActive(item.path) ? "bg-sidebar-accent text-white" : "text-sidebar-foreground/80 hover:text-white"}
                >
                  <Link to={item.path} className="flex items-center gap-3 px-3 py-2">
                    {item.icon}
                    <span>{item.label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter className="py-4 px-2 border-t border-sidebar-border space-y-4">
          <div className="px-2">
            <UserProfile />
          </div>
          <div className="flex justify-center">
            <Button 
              variant="destructive" 
              size="sm" 
              className="w-full"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              Log Out
            </Button>
          </div>
        </SidebarFooter>
      </Sidebar>
      <div className="fixed top-4 left-4 z-50">
        <SidebarTrigger>
          <Button 
            variant="outline" 
            size="icon" 
            className={`rounded-full ${!open ? 'bg-white shadow-md' : 'bg-transparent border-none'}`}
          >
            <ChevronLeft className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
          </Button>
        </SidebarTrigger>
      </div>
    </>
  );
}
