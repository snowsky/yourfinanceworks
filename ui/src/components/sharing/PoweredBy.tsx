import { useTranslation } from 'react-i18next';

/** Footer credit on tenant-branded public pages (client portal, shared links). */
export function PoweredBy({ className = '' }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <p className={`text-center text-xs text-muted-foreground ${className}`}>
      {t('common.powered_by')}{' '}
      <a href="/" className="underline hover:text-foreground">YourFinanceWORKS</a>
    </p>
  );
}
