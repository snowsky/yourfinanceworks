import React from 'react';
import { MobileSidebar } from './MobileSidebar';

interface MobileLayoutProps {
  children: React.ReactNode;
}

export function MobileLayout({ children }: MobileLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <MobileSidebar />
      <main className="flex-1 p-4 overflow-auto">{children}</main>
    </div>
  );
}
