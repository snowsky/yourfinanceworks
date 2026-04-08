import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Loader2, Trash2, RotateCcw, FileText } from 'lucide-react';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { formatStatus, type DeletedBankStatement } from '@/lib/api';

interface RecycleBinSectionProps {
  showRecycleBin: boolean;
  setShowRecycleBin: (v: boolean) => void;
  deletedStatements: DeletedBankStatement[];
  recycleBinLoading: boolean;
  recycleBinTotalCount: number;
  recycleBinCurrentPage: number;
  recycleBinPageSize: number;
  setRecycleBinCurrentPage: (fn: (prev: number) => number) => void;
  onRestore: (id: number) => void;
  onPermanentlyDelete: (id: number) => void;
  onEmptyRecycleBin: () => void;
}

export function RecycleBinSection({
  showRecycleBin,
  setShowRecycleBin,
  deletedStatements,
  recycleBinLoading,
  recycleBinTotalCount,
  recycleBinCurrentPage,
  recycleBinPageSize,
  setRecycleBinCurrentPage,
  onRestore,
  onPermanentlyDelete,
  onEmptyRecycleBin,
}: RecycleBinSectionProps) {
  const { t } = useTranslation();
  const totalPages = Math.ceil(recycleBinTotalCount / recycleBinPageSize);

  return (
    <Collapsible open={showRecycleBin} onOpenChange={setShowRecycleBin}>
      <CollapsibleContent>
        <ProfessionalCard className="slide-in mb-8 border-l-4 border-l-destructive overflow-hidden" variant="elevated">
          <div className="absolute top-0 right-0 w-40 h-40 bg-destructive/5 rounded-full -mr-20 -mt-20 blur-3xl"></div>
          <div className="relative space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20">
                  <Trash2 className="h-6 w-6 text-destructive" />
                </div>
                <div>
                  <h3 className="font-bold text-xl text-foreground">{t('statementRecycleBin.title', { defaultValue: 'Recycle Bin' })}</h3>
                  <p className="text-sm text-muted-foreground">
                    {recycleBinTotalCount} {t('statementRecycleBin.items', 'items')} • Recover or permanently delete statements
                  </p>
                </div>
              </div>
              {deletedStatements.length > 0 && (
                <ProfessionalButton
                  variant="destructive"
                  size="default"
                  onClick={onEmptyRecycleBin}
                >
                  <Trash2 className="h-4 w-4" />
                  {t('statementRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
                </ProfessionalButton>
              )}
            </div>
            <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30">
                    <TableHead className="font-bold text-foreground">{t('statements.filename')}</TableHead>
                    <TableHead className="font-bold text-foreground">{t('statements.review_status.label')}</TableHead>
                    <TableHead className="font-bold text-foreground">{t('statements.transactions')}</TableHead>
                    <TableHead className="font-bold text-foreground">{t('statementRecycleBin.deleted_at')}</TableHead>
                    <TableHead className="font-bold text-foreground">{t('statementRecycleBin.deleted_by')}</TableHead>
                    <TableHead className="w-[100px] font-bold text-foreground text-right">{t('statementRecycleBin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recycleBinLoading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex justify-center items-center gap-2">
                          <Loader2 className="h-5 w-5 animate-spin text-primary" />
                          <span className="text-muted-foreground">{t('statementRecycleBin.loading', { defaultValue: 'Loading...' })}</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : deletedStatements.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-32 text-center">
                        <div className="flex flex-col items-center justify-center gap-3">
                          <div className="p-4 rounded-full bg-muted/50">
                            <Trash2 className="h-8 w-8 text-muted-foreground/50" />
                          </div>
                          <p className="text-muted-foreground font-medium">{t('statementRecycleBin.recycle_bin_empty', { defaultValue: 'Recycle bin is empty' })}</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    deletedStatements.map((statement) => (
                      <TableRow key={statement.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                        <TableCell className="font-semibold text-foreground">
                          <span className="inline-flex items-center gap-2">
                            <FileText className="h-4 w-4 text-primary/60" />
                            {statement.original_filename}
                          </span>
                        </TableCell>
                        <TableCell className="text-foreground">
                          <Badge variant="outline" className="capitalize font-medium">
                            {formatStatus(statement.status)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-foreground">{statement.extracted_count}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">{statement.deleted_at ? format(new Date(statement.deleted_at), 'PP p') : 'N/A'}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">{statement.deleted_by_username || t('common.unknown')}</TableCell>
                        <TableCell>
                          <div className="flex gap-2 justify-end">
                            <ProfessionalButton
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => onRestore(statement.id)}
                              title="Restore statement"
                              className="hover:bg-success/10 hover:text-success"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </ProfessionalButton>
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  className="hover:bg-destructive/10 hover:text-destructive"
                                  title="Permanently delete"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </ProfessionalButton>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>{t('statementRecycleBin.permanently_delete_confirm_title', { defaultValue: 'Permanently Delete Statement' })}</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    {t('statementRecycleBin.permanently_delete_confirm_description', { defaultValue: 'Are you sure you want to permanently delete this statement? This action cannot be undone.' })}
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => onPermanentlyDelete(statement.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                                    <Trash2 className="mr-2 h-4 w-4" />
                                    {t('statementRecycleBin.permanently_delete', { defaultValue: 'Permanently Delete' })}
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
            {totalPages > 1 && (
              <div className="mt-4">
                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        onClick={() => setRecycleBinCurrentPage(prev => Math.max(1, prev - 1))}
                        className={recycleBinCurrentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum = recycleBinCurrentPage;
                      if (totalPages <= 5) pageNum = i + 1;
                      else if (recycleBinCurrentPage <= 3) pageNum = i + 1;
                      else if (recycleBinCurrentPage >= totalPages - 2) pageNum = totalPages - 4 + i;
                      else pageNum = recycleBinCurrentPage - 2 + i;
                      return (
                        <PaginationItem key={pageNum}>
                          <PaginationLink
                            onClick={() => setRecycleBinCurrentPage(() => pageNum)}
                            isActive={recycleBinCurrentPage === pageNum}
                            className="cursor-pointer"
                          >
                            {pageNum}
                          </PaginationLink>
                        </PaginationItem>
                      );
                    })}
                    <PaginationItem>
                      <PaginationNext
                        onClick={() => setRecycleBinCurrentPage(prev => Math.min(totalPages, prev + 1))}
                        className={recycleBinCurrentPage >= totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            )}
          </div>
        </ProfessionalCard>
      </CollapsibleContent>
    </Collapsible>
  );
}
