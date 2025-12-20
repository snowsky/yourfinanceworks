import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { approvalApi } from '@/lib/api';
import {
    Search,
    Calendar,
    DollarSign,
    User,
    Eye,
    CheckCircle,
    XCircle,
    FileText
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { useTranslation } from 'react-i18next';

interface ProcessedInvoicesListProps {
    onViewDetails?: (invoiceId: number) => void;
}

export function ProcessedInvoicesList({ onViewDetails }: ProcessedInvoicesListProps) {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [invoices, setInvoices] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [searchQuery, setSearchQuery] = useState('');

    const pageSize = 10;

    const fetchInvoices = async () => {
        try {
            setLoading(true);
            const skip = page * pageSize;
            const response = await approvalApi.getProcessedInvoices({
                skip,
                limit: pageSize
            });

            const data = response.invoices || [];
            setInvoices(data);
            setTotal(response.total || 0);
        } catch (error: any) {
            console.error('Failed to fetch processed invoices:', error);
            const errorMessage = error?.message || 'Failed to load processed invoices';
            toast.error(errorMessage);
            setInvoices([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchInvoices();
    }, [page]);

    const handleViewDetails = (invoiceId: number) => {
        if (onViewDetails) {
            onViewDetails(invoiceId);
        } else {
            navigate(`/invoices/view/${invoiceId}`);
        }
    };

    const formatCurrency = (amount: number, currency: string = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
        }).format(amount);
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'approved':
                return (
                    <Badge variant="default" className="bg-green-100 text-green-800 hover:bg-green-100">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        {t('approvalDashboard.approved')}
                    </Badge>
                );
            case 'rejected':
                return (
                    <Badge variant="destructive">
                        <XCircle className="w-3 h-3 mr-1" />
                        {t('approvalDashboard.rejected')}
                    </Badge>
                );
            default:
                return (
                    <Badge variant="secondary">
                        {status}
                    </Badge>
                );
        }
    };

    const totalPages = Math.ceil(total / pageSize);

    // Simple filtering for the search query if backend doesn't support it yet
    const filteredInvoices = invoices.filter(invoice =>
        invoice.number.toLowerCase().includes(searchQuery.toLowerCase()) ||
        invoice.client_name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-4">
            {/* Search */}
            <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                        <Input
                            placeholder={t('approvalDashboard.search_invoices_placeholder', { defaultValue: 'Search by invoice number or client...' })}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10"
                        />
                    </div>
                </div>
            </div>

            {/* Invoices List */}
            <div className="space-y-2">
                {loading ? (
                    Array.from({ length: 5 }).map((_, index) => (
                        <Card key={index}>
                            <CardContent className="p-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex-1">
                                        <Skeleton className="h-4 w-48 mb-2" />
                                        <Skeleton className="h-3 w-32" />
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <Skeleton className="h-6 w-16" />
                                        <Skeleton className="h-8 w-20" />
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))
                ) : filteredInvoices.length === 0 ? (
                    <Card className="border-dashed">
                        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                            <div className="bg-primary/5 p-6 rounded-full mb-6 ring-8 ring-primary/2">
                                <FileText className="h-12 w-12 text-primary/40" />
                            </div>
                            <h3 className="text-xl font-semibold mb-2">
                                {t('approvalDashboard.no_processed_invoices_title', 'No processed invoices')}
                            </h3>
                            <p className="text-muted-foreground max-w-sm mx-auto mb-8">
                                {t('approvalDashboard.no_processed_invoices_description', "You haven't approved or rejected any invoices yet. Your approval history will appear here.")}
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    filteredInvoices.map((invoice) => (
                        <Card key={invoice.id} className="hover:shadow-md transition-shadow">
                            <CardContent className="p-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-3 mb-2">
                                            <h3 className="font-medium text-gray-900 truncate">
                                                {invoice.number} - {invoice.client_name}
                                            </h3>
                                            {getStatusBadge(invoice.status)}
                                        </div>

                                        <div className="flex items-center gap-4 text-sm text-gray-600">
                                            <div className="flex items-center gap-1">
                                                <DollarSign className="h-3 w-3" />
                                                {formatCurrency(invoice.amount, invoice.currency)}
                                            </div>

                                            <div className="flex items-center gap-1">
                                                <User className="h-3 w-3" />
                                                {invoice.client_name}
                                            </div>

                                            <div className="flex items-center gap-1">
                                                <Calendar className="h-3 w-3" />
                                                {invoice.decided_at && !isNaN(new Date(invoice.decided_at).getTime())
                                                    ? formatDistanceToNow(new Date(invoice.decided_at), { addSuffix: true })
                                                    : 'Unknown date'
                                                }
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleViewDetails(invoice.id)}
                                        >
                                            <Eye className="h-4 w-4 mr-2" />
                                            {t('approvalDashboard.view_details')}
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-600">
                        {t('approvalDashboard.showing')} {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} {t('approvalDashboard.of')} {total} {t('approvalDashboard.invoices')}
                    </div>

                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage(prev => Math.max(0, prev - 1))}
                            disabled={page === 0}
                        >
                            {t('approvalHelp.previous')}
                        </Button>

                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage(prev => Math.min(totalPages - 1, prev + 1))}
                            disabled={page >= totalPages - 1}
                        >
                            {t('approvalHelp.next')}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
