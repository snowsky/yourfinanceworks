import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, RotateCcw, ChevronDown, Loader2, FileText, ChevronUp } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { PageHeader } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";

interface DeletedStatement {
  id: number;
  original_filename: string;
  status: string;
  extracted_count: number;
  deleted_at: string;
  deleted_by_username: string;
  created_by_username: string;
}

const StatementRecycleBin = () => {
  const { t } = useTranslation();
  const [deletedStatements, setDeletedStatements] = useState<DeletedStatement[]>([]);
  const [loading, setLoading] = useState(true);
  const [permanentDeleteModalOpen, setPermanentDeleteModalOpen] = useState(false);
  const [statementToDelete, setStatementToDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);
  const [isBinCollapsed, setIsBinCollapsed] = useState(true);
  const [userInteracted, setUserInteracted] = useState(false);

  useEffect(() => {
    fetchDeletedStatements();
  }, []);

  useEffect(() => {
    // Auto-collapse when bin is empty and not loading, but only if user hasn't interacted
    if (!loading && deletedStatements.length === 0 && !userInteracted) {
      setIsBinCollapsed(true);
    }
  }, [deletedStatements, loading, userInteracted]);

  const fetchDeletedStatements = async () => {
    try {
      setLoading(true);
      const data = await api.get<DeletedStatement[]>('/statements/recycle-bin');
      setDeletedStatements(data);
    } catch (error) {
      console.error('Failed to fetch deleted statements:', error);
      toast.error(t('statementRecycleBin.failed_to_load_deleted_statements'));
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (statementId: number) => {
    try {
      await api.post(`/statements/${statementId}/restore`, { new_status: 'processed' });
      toast.success(t('statementRecycleBin.statement_restored_successfully'));
      fetchDeletedStatements();
    } catch (error) {
      console.error('Failed to restore statement:', error);
      toast.error(t('statementRecycleBin.failed_to_restore_statement'));
    }
  };

  const handlePermanentDelete = (statementId: number) => {
    setStatementToDelete(statementId);
    setPermanentDeleteModalOpen(true);
  };

  const confirmPermanentDelete = async () => {
    if (!statementToDelete) return;

    try {
      await api.delete(`/statements/${statementToDelete}/permanent`);
      toast.success(t('statementRecycleBin.statement_permanently_deleted'));
      fetchDeletedStatements();
    } catch (error) {
      console.error('Failed to permanently delete statement:', error);
      let errorMessage = error instanceof Error ? error.message : t('statementRecycleBin.failed_to_permanently_delete_statement');
      toast.error(errorMessage);
    } finally {
      setPermanentDeleteModalOpen(false);
      setStatementToDelete(null);
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const handleUserInteraction = () => {
    setUserInteracted(true);
  };

  const confirmEmptyRecycleBin = async () => {
    try {
      await api.post('/statements/recycle-bin/empty');
      toast.success(t('statementRecycleBin.recycle_bin_emptied_successfully'));
      fetchDeletedStatements();
    } catch (error) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(t('statementRecycleBin.failed_to_empty_recycle_bin'));
    } finally {
      setEmptyRecycleBinModalOpen(false);
    }
  };

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        <PageHeader
          title={t('recycleBin.title')}
          description={t('statementRecycleBin.description')}
          icon={<Trash2 className="h-8 w-8 text-primary" />}
        />

        <Collapsible
          open={!isBinCollapsed}
          onOpenChange={(open) => {
            setIsBinCollapsed(!open);
            handleUserInteraction();
          }}
          className="space-y-4"
        >
          <ProfessionalCard className="slide-in border-l-4 border-l-destructive overflow-hidden" variant="elevated">
            <div className="absolute top-0 right-0 w-40 h-40 bg-destructive/5 rounded-full -mr-20 -mt-20 blur-3xl"></div>
            <div className="relative space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20">
                    <Trash2 className="h-6 w-6 text-destructive" />
                  </div>
                  <CollapsibleTrigger asChild>
                    <div className="cursor-pointer group flex items-center gap-3">
                      <div>
                        <h3 className="font-bold text-xl text-foreground group-hover:text-primary transition-colors">
                          {t('statementRecycleBin.deleted_statements')}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {deletedStatements.length} {t('statementRecycleBin.items', 'items')}
                        </p>
                      </div>
                      <ChevronDown className={`h-5 w-5 text-muted-foreground transition-transform duration-300 ${isBinCollapsed ? '' : 'rotate-180'}`} />
                    </div>
                  </CollapsibleTrigger>
                </div>
                {deletedStatements.length > 0 && (
                  <ProfessionalButton
                    variant="destructive"
                    size="default"
                    onClick={handleEmptyRecycleBin}
                    className="shadow-lg"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {t('statementRecycleBin.empty_recycle_bin')}
                  </ProfessionalButton>
                )}
              </div>

              <CollapsibleContent>
                <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm mt-4">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30">
                        <TableHead className="font-bold text-foreground">{t('statementRecycleBin.filename')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('statementRecycleBin.status')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('statementRecycleBin.transactions')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('statementRecycleBin.deleted_at')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('statementRecycleBin.deleted_by')}</TableHead>
                        <TableHead className="w-[120px] font-bold text-foreground text-right">{t('statementRecycleBin.actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loading ? (
                        <TableRow>
                          <TableCell colSpan={6} className="h-24 text-center">
                            <div className="flex justify-center items-center gap-2">
                              <Loader2 className="h-5 w-5 animate-spin text-primary" />
                              <span className="text-muted-foreground">{t('statementRecycleBin.loading_deleted_statements')}</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : deletedStatements.length > 0 ? (
                        deletedStatements.map((statement) => (
                          <TableRow key={statement.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                            <TableCell className="font-semibold text-foreground">
                              <div className="flex flex-col">
                                <span className="inline-flex items-center gap-2">
                                  <FileText className="h-4 w-4 text-primary/60" />
                                  {statement.original_filename}
                                </span>
                                <span className="text-xs text-muted-foreground mt-0.5">
                                  {t('statementRecycleBin.created_by', { user: statement.created_by_username || t('statementRecycleBin.unknown') })}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="capitalize font-medium">
                                {statement.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-foreground tracking-tight font-medium">
                              {statement.extracted_count}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">{formatDate(statement.deleted_at)}</TableCell>
                            <TableCell className="text-muted-foreground text-sm font-medium">
                              {statement.deleted_by_username || t('statementRecycleBin.unknown')}
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-2 justify-end">
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handleRestore(statement.id)}
                                  className="hover:bg-success/10 hover:text-success"
                                  title={t('statementRecycleBin.restore_statement')}
                                >
                                  <RotateCcw className="h-4 w-4" />
                                </ProfessionalButton>
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handlePermanentDelete(statement.id)}
                                  className="hover:bg-destructive/10 hover:text-destructive"
                                  title={t('statementRecycleBin.permanently_delete')}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </ProfessionalButton>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={6} className="h-32 text-center">
                            <div className="flex flex-col items-center justify-center gap-3">
                              <div className="p-4 rounded-full bg-muted/50">
                                <Trash2 className="h-8 w-8 text-muted-foreground/50" />
                              </div>
                              <p className="text-muted-foreground font-medium">{t('statementRecycleBin.recycle_bin_empty')}</p>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CollapsibleContent>
            </div>
          </ProfessionalCard>
        </Collapsible>
      </div>

      {/* Permanent Delete Modal */}
      <AlertDialog open={permanentDeleteModalOpen} onOpenChange={setPermanentDeleteModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('statementRecycleBin.permanent_delete_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('statementRecycleBin.permanent_delete_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmPermanentDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('statementRecycleBin.permanent_delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Empty Recycle Bin Modal */}
      <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('statementRecycleBin.empty_recycle_bin_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('statementRecycleBin.empty_recycle_bin_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('statementRecycleBin.empty_recycle_bin')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default StatementRecycleBin;
