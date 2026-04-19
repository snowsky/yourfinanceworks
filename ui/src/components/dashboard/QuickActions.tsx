import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
    Plus,
    FileText,
    Users,
    DollarSign,
    Upload,
    Clock,
    AlertCircle,
    Package,
    ListChecks,
    BarChart,
    ArrowRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { canPerformActions, getCurrentUser } from '@/utils/auth';
import { approvalApi } from '@/lib/api';
import { toast } from 'sonner';
import { QuickActionsLoading } from './QuickActionsLoading';

interface QuickAction {
    id: string;
    title: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    href?: string;
    onClick?: () => void;
    variant?: 'default' | 'primary' | 'success' | 'warning';
    badge?: string | number;
    disabled?: boolean;
    requiresPermission?: boolean;
}

interface PendingItem {
    id: number;
    type: 'expense' | 'invoice' | 'approval';
    title: string;
    amount?: string;
    daysOverdue?: number;
    priority?: 'high' | 'medium' | 'low';
}

export function QuickActions() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [pendingApprovals, setPendingApprovals] = useState<number>(0);
    const [pendingItems, setPendingItems] = useState<PendingItem[]>([]);
    const [loading, setLoading] = useState(true);
    const user = getCurrentUser();
    const canPerform = canPerformActions();

    // Fetch pending items and approvals
    useEffect(() => {
        const fetchPendingData = async () => {
            try {
                setLoading(true);

                // Fetch pending approvals count
                if (user?.role === 'admin' || user?.role === 'user') {
                    try {
                        const response = await approvalApi.getPendingApprovals();
                        const approvals = response.approvals || [];
                        setPendingApprovals(approvals.length);

                        // Convert approvals to pending items
                        const approvalItems: PendingItem[] = approvals.slice(0, 3).map(approval => ({
                            id: approval.id,
                            type: 'approval' as const,
                            title: `Expense #${approval.expense_id}`,
                            amount: `$${approval.expense?.amount || 0}`,
                            priority: 'high' as const
                        }));

                        setPendingItems(approvalItems);
                    } catch (error) {
                        console.error('Failed to fetch pending approvals:', error);
                    }
                }

                // You can add more pending items here (overdue invoices, etc.)

            } catch (error) {
                console.error('Failed to fetch pending data:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchPendingData();
    }, [user?.role]);

    const primaryActions: QuickAction[] = [
        {
            id: 'new-expense',
            title: t('dashboard.quick_actions.new_expense', 'New Expense'),
            description: t('dashboard.quick_actions.new_expense_desc', 'Record a new business expense'),
            icon: Plus,
            href: '/expenses/new',
            variant: 'primary',
            requiresPermission: true
        },
        {
            id: 'new-invoice',
            title: t('dashboard.quick_actions.new_invoice', 'Create Invoice'),
            description: t('dashboard.quick_actions.new_invoice_desc', 'Generate a new client invoice'),
            icon: FileText,
            href: '/invoices/new',
            variant: 'primary',
            requiresPermission: true
        },
        {
            id: 'import-expenses',
            title: t('dashboard.quick_actions.import_expenses', 'Import Expenses'),
            description: t('dashboard.quick_actions.import_expenses_desc', 'Upload receipts and documents'),
            icon: Upload,
            href: '/expenses/import',
            variant: 'default',
            requiresPermission: true
        },
        {
            id: 'add-client',
            title: t('dashboard.quick_actions.add_client', 'Add Client'),
            description: t('dashboard.quick_actions.add_client_desc', 'Register a new client'),
            icon: Users,
            href: '/clients/new',
            variant: 'default',
            requiresPermission: true
        }
    ];

    const secondaryActions: QuickAction[] = [
        {
            id: 'pending-approvals',
            title: t('dashboard.quick_actions.pending_approvals', 'Pending Approvals'),
            description: t('dashboard.quick_actions.pending_approvals_desc', 'Review expense approvals'),
            icon: ListChecks,
            href: '/approvals',
            badge: pendingApprovals > 0 ? pendingApprovals : undefined,
            variant: pendingApprovals > 0 ? 'warning' : 'default'
        },
        {
            id: 'inventory',
            title: t('dashboard.quick_actions.inventory', 'Inventory'),
            description: t('dashboard.quick_actions.inventory_desc', 'Manage inventory items'),
            icon: Package,
            href: '/inventory',
            variant: 'default'
        },
        {
            id: 'reports',
            title: t('dashboard.quick_actions.reports', 'Generate Reports'),
            description: t('dashboard.quick_actions.reports_desc', 'Create financial reports'),
            icon: BarChart,
            href: '/reports',
            variant: 'default'
        },
        {
            id: 'reminders',
            title: t('dashboard.quick_actions.reminders', 'Reminders'),
            description: t('dashboard.quick_actions.reminders_desc', 'Manage payment reminders'),
            icon: Clock,
            href: '/reminders',
            variant: 'default',
            requiresPermission: true
        }
    ];

    const handleActionClick = (action: QuickAction) => {
        if (action.disabled) return;

        if (action.requiresPermission && !canPerform) {
            toast.error('You do not have permission to perform this action');
            return;
        }

        if (action.onClick) {
            action.onClick();
        } else if (action.href) {
            navigate(action.href);
        }
    };

    const getActionStyles = (variant: string) => {
        switch (variant) {
            case 'primary':
                return 'border-primary/40 bg-primary/10 text-foreground hover:bg-primary/15';
            case 'success':
                return 'border-success/40 bg-success/10 text-foreground hover:bg-success/15';
            case 'warning':
                return 'border-warning/45 bg-warning/10 text-foreground hover:bg-warning/15';
            default:
                return 'border-border bg-card text-foreground hover:bg-muted/40';
        }
    };

    const getBadgeStyles = (variant: string) => {
        switch (variant) {
            case 'warning':
                return 'bg-orange-100 text-orange-800 border-orange-200';
            case 'success':
                return 'bg-green-100 text-green-800 border-green-200';
            default:
                return 'bg-blue-100 text-blue-800 border-blue-200';
        }
    };

    if (loading) {
        return <QuickActionsLoading />;
    }

    return (
        <div className="space-y-6">
            {/* Primary Actions */}
            <div className="space-y-4">
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
                        {t('dashboard.quick_actions.core_actions', 'Core Actions')}
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {primaryActions.map((action) => {
                            const Icon = action.icon;
                            const isDisabled = action.requiresPermission && !canPerform;

                            return (
                                <Button
                                    key={action.id}
                                    onClick={() => handleActionClick(action)}
                                    disabled={isDisabled}
                                    className={cn(
                                        "group h-auto w-full rounded-xl border p-4 flex items-start gap-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md focus:ring-2 focus:ring-offset-2",
                                        getActionStyles(action.variant || 'default')
                                    )}
                                    aria-label={`${action.title}: ${action.description}`}
                                >
                                    <div className="mt-0.5 rounded-lg bg-background/70 p-2 ring-1 ring-border/60">
                                        <Icon className="h-4 w-4 text-foreground/80" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <div className="font-semibold text-sm leading-tight">{action.title}</div>
                                        <div className="mt-1 text-xs text-muted-foreground leading-relaxed">{action.description}</div>
                                    </div>
                                    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                                </Button>
                            );
                        })}
                    </div>
                </div>

                <Separator className="my-4" />

                <div className="space-y-2">
                    <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
                        {t('dashboard.quick_actions.operations', 'Operations')}
                    </h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                        {secondaryActions.map((action) => {
                            const Icon = action.icon;

                            return (
                                <Button
                                    key={action.id}
                                    variant="ghost"
                                    onClick={() => handleActionClick(action)}
                                    className="relative h-auto min-h-[92px] rounded-xl border border-border/70 bg-background/60 p-3 flex flex-col items-start gap-2 text-foreground hover:text-foreground focus:text-foreground hover:bg-muted/50 hover:border-primary/30 transition-all duration-200"
                                >
                                    {action.badge && (
                                        <Badge className={cn(
                                            "absolute top-2 right-2 h-5 min-w-5 px-1.5 flex items-center justify-center text-xs",
                                            getBadgeStyles(action.variant || 'default')
                                        )}>
                                            {action.badge}
                                        </Badge>
                                    )}
                                    <div className={cn(
                                        "rounded-lg p-2 ring-1 ring-border/60",
                                        action.variant === 'warning' ? 'bg-warning/10' : 'bg-muted/60'
                                    )}>
                                        <Icon className={cn(
                                            "h-4 w-4",
                                            action.variant === 'warning' ? 'text-warning' : 'text-foreground/80'
                                        )} />
                                    </div>
                                    <span className="text-xs font-semibold text-left leading-tight break-words whitespace-normal">
                                        {action.title}
                                    </span>
                                </Button>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Pending Items */}
            {pendingItems.length > 0 && (
                <Card className="border border-warning/40 bg-warning/5 rounded-xl shadow-sm">
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <AlertCircle className="h-5 w-5 text-warning" />
                                <CardTitle className="text-base font-semibold">
                                    {t('dashboard.pending_items.title', 'Needs Attention')}
                                </CardTitle>
                            </div>
                            <Link
                                to="/approvals"
                                className="text-sm text-primary hover:text-primary/80 flex items-center gap-1"
                            >
                                {t('dashboard.pending_items.view_all', 'View All')}
                                <ArrowRight className="h-3 w-3" />
                            </Link>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {pendingItems.map((item) => (
                                <div key={`${item.type}-${item.id}`} className="flex items-center justify-between p-3 bg-card rounded-lg border border-warning/30">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-warning/10 rounded-lg">
                                            {item.type === 'approval' && <ListChecks className="h-4 w-4 text-warning" />}
                                            {item.type === 'expense' && <DollarSign className="h-4 w-4 text-warning" />}
                                            {item.type === 'invoice' && <FileText className="h-4 w-4 text-warning" />}
                                        </div>
                                        <div>
                                            <div className="font-medium text-sm">{item.title}</div>
                                            {item.amount && (
                                                <div className="text-xs text-muted-foreground">{item.amount}</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {item.priority === 'high' && (
                                            <Badge variant="destructive" className="text-xs">High</Badge>
                                        )}
                                        <Button size="sm" variant="outline" className="text-xs">
                                            {t('dashboard.pending_items.review', 'Review')}
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
