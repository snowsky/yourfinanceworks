import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { useFeatures } from '@/contexts/FeatureContext';

interface StatementUploadButtonProps {
  onUpload: () => void;
}

export function StatementUploadButton({ onUpload }: StatementUploadButtonProps) {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const hasFeature = isFeatureEnabled('ai_bank_statement');

  return (
    <ProfessionalButton onClick={onUpload} disabled={!hasFeature} className={!hasFeature ? 'opacity-50 cursor-not-allowed' : ''}>
      <Plus className="w-4 h-4 mr-2" />
      {t('statements.new_statement', { defaultValue: 'New Statement' })}
    </ProfessionalButton>
  );
}
