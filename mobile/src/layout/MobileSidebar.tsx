import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  FileText,
  CreditCard,
  Settings,
  Menu,
} from 'lucide-react';

export function MobileSidebar() {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);

  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
    { icon: Users, label: 'Clients', path: '/clients' },
    { icon: FileText, label: 'Invoices', path: '/invoices' },
    { icon: CreditCard, label: 'Payments', path: '/payments' },
    { icon: Settings, label: 'Settings', path: '/settings' },
  ];

  return (
    <div className="border-b bg-background">
      <div className="flex items-center justify-between p-4">
        <button onClick={() => setIsOpen(!isOpen)}>
          <Menu className="h-6 w-6" />
        </button>
        <h1 className="text-lg font-semibold">Invoice App</h1>
      </div>
      {isOpen && (
        <nav className="flex flex-col space-y-2 p-4">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center space-x-2 p-2 rounded-md ${
                location.pathname === item.path
                  ? 'bg-primary text-white'
                  : 'text-muted-foreground'
              }`}
            >
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
