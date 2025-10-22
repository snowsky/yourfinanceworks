import React from 'react';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarProvider } from '@/components/ui/sidebar';
import { useTranslation } from "react-i18next";
import { JoinRequestsTable } from '@/components/JoinRequestsTable';

const OrganizationJoinRequestsContent: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('organizationJoinRequests.title')}</h1>
          <p className="text-gray-600">{t('organizationJoinRequests.description')}</p>
        </div>
      </div>

      <JoinRequestsTable showAsCard={false} />
    </div>
  );
};

const OrganizationJoinRequests: React.FC = () => {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen">
        <div className="w-64 flex-shrink-0">
          <AppSidebar />
        </div>
        <div className="flex-1">
          <OrganizationJoinRequestsContent />
        </div>
      </div>
    </SidebarProvider>
  );
};

export default OrganizationJoinRequests;
