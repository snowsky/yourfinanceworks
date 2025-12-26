import React from 'react';
import { useTranslation } from "react-i18next";
import { JoinRequestsTable } from '@/components/JoinRequestsTable';

const OrganizationJoinRequestsContent: React.FC = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="p-6 space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('organizationJoinRequests.title')}</h1>
            <p className="text-gray-600">{t('organizationJoinRequests.description')}</p>
          </div>
        </div>

        <JoinRequestsTable showAsCard={false} />
      </div>
    </>
  );
};

const OrganizationJoinRequests: React.FC = () => {
  return (
    <OrganizationJoinRequestsContent />
  );
};

export default OrganizationJoinRequests;
