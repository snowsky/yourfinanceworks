import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, RotateCcw } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

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

  useEffect(() => {
    fetchDeletedStatements();
  }, []);

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
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Trash2 className="h-8 w-8" />
              {t('statementRecycleBin.title')}
            </h1>
            <p className="text-muted-foreground">{t('statementRecycleBin.description')}</p>
          </div>
          {deletedStatements.length > 0 && (
            <Button
              variant="destructive"
              onClick={handleEmptyRecycleBin}
              className="sm:self-end whitespace-nowrap"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t('statementRecycleBin.empty_recycle_bin')}
            </Button>
          )}
        </div>

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <CardTitle>{t('statementRecycleBin.deleted_statements')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('statementRecycleBin.filename')}</TableHead>
                    <TableHead>{t('statementRecycleBin.status')}</TableHead>
                    <TableHead>{t('statementRecycleBin.transactions')}</TableHead>
                    <TableHead>{t('statementRecycleBin.deleted_at')}</TableHead>
                    <TableHead>{t('statementRecycleBin.deleted_by')}</TableHead>
                    <TableHead className="w-[150px]">{t('statementRecycleBin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        {t('statementRecycleBin.loading_deleted_statements')}
                      </TableCell>
                    </TableRow>
                  ) : deletedStatements.length > 0 ? (
                    deletedStatements.map((statement) => (
                      <TableRow key={statement.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">
                          <div>
                            <div className="font-medium truncate max-w-[200px]" title={statement.original_filename}>
                              {statement.original_filename}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {t('statementRecycleBin.created_by', { user: statement.created_by_username || t('statementRecycleBin.unknown') })}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {statement.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {statement.extracted_count}
                        </TableCell>
                        <TableCell>{formatDate(statement.deleted_at)}</TableCell>
                        <TableCell>{statement.deleted_by_username || t('statementRecycleBin.unknown')}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRestore(statement.id)}
                              className="text-green-600 hover:text-green-700 hover:bg-green-50"
                              title={t('statementRecycleBin.restore_statement')}
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handlePermanentDelete(statement.id)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              title={t('statementRecycleBin.permanently_delete')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex flex-col items-center gap-2">
                          <Trash2 className="h-8 w-8 text-muted-foreground" />
                          <p>{t('statementRecycleBin.recycle_bin_empty')}</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
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
