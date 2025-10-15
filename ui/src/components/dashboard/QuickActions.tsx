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
    CheckCircle,
    AlertCircle,
    TrendingUp,
    Package,
    ListChecks,
    BarChart,
    ArrowRight,
    Zap
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { canPerformActions, getCurrentUser } from '@/utils/auth';
import { dashboardApi, approvalApi } from '@/lib/api';
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
                return 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:from-blue-600 hover:to-indigo-700 border-0';
            case 'success':
                return 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:from-green-600 hover:to-emerald-700 border-0';
            case 'warning':
                return 'bg-gradient-to-r from-orange-500 to-amber-600 text-white hover:from-orange-600 hover:to-amber-700 border-0';
            default:
                return 'bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 hover:text-gray-900';
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
            <Card className="border-0 shadow-lg bg-gradient-to-br from-slate-50 to-white">
                <CardHeader className="pb-4">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-lg">
                            <Zap className="h-5 w-5 text-white" />
                        </div>
                        <div>
                            <CardTitle className="text-lg font-semibold">
                                {t('dashboard.quick_actions.title', 'Quick Actions')}
                            </CardTitle>
                            <p className="text-sm text-muted-foreground">
                                {t('dashboard.quick_actions.subtitle', 'Common tasks and shortcuts')}
                            </p>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Primary action buttons */}
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
                                        "h-auto p-4 flex flex-col items-start gap-2 text-left transition-all duration-200 hover:scale-105 hover:shadow-md focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
                                        getActionStyles(action.variant || 'default')
                                    )}
                                    aria-label={`${action.title}: ${action.description}`}
                                >
                                    <div className="flex items-center gap-3 w-full">
                                        <div className={cn(
                                            "p-2 rounded-lg",
                                            action.variant === 'primary' ? 'bg-white/20' : 'bg-gray-100'
                                        )}>
                                            <Icon className={cn(
                                                "h-5 w-5",
                                                action.variant === 'primary' ? 'text-white' : 'text-gray-600'
                                            )} />
                                        </div>
                                        <div className="flex-1">
                                            <div className="font-medium text-sm">{action.title}</div>
                                            <div className={cn(
                                                "text-xs opacity-80",
                                                action.variant === 'primary' ? 'text-white' : 'text-muted-foreground'
                                            )}>
                                                {action.description}
                                            </div>
                                        </div>
                                        {action.badge && (
                                            <Badge className={getBadgeStyles(action.variant || 'default')}>
                                                {action.badge}
                                            </Badge>
                                        )}
                                    </div>
                                </Button>
                            );
                        })}
                    </div>

                    <Separator className="my-4" />

                    {/* Secondary actions */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                        {secondaryActions.map((action) => {
                            const Icon = action.icon;

                            return (
                                <Button
                                    key={action.id}
                                    variant="ghost"
                                    onClick={() => handleActionClick(action)}
                                    className="h-auto p-3 flex flex-col items-center gap-2 hover:bg-gray-50 transition-all duration-200 hover:scale-105 relative"
                                >
                                    {action.badge && (
                                        <Badge className={cn(
                                            "absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center text-xs",
                                            getBadgeStyles(action.variant || 'default')
                                        )}>
                                            {action.badge}
                                        </Badge>
                                    )}
                                    <div className={cn(
                                        "p-2 rounded-lg",
                                        action.variant === 'warning' ? 'bg-orange-100' : 'bg-gray-100'
                                    )}>
                                        <Icon className={cn(
                                            "h-4 w-4",
                                            action.variant === 'warning' ? 'text-orange-600' : 'text-gray-600'
                                        )} />
                                    </div>
                                    <span className="text-xs font-medium text-center leading-tight">
                                        {action.title}
                                    </span>
                                </Button>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>

            {/* Pending Items */}
            {pendingItems.length > 0 && (
                <Card className="border-l-4 border-l-orange-500 bg-orange-50/50">
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <AlertCircle className="h-5 w-5 text-orange-600" />
                                <CardTitle className="text-lg font-semibold text-orange-900">
                                    {t('dashboard.pending_items.title', 'Needs Attention')}
                                </CardTitle>
                            </div>
                            <Link
                                to="/approvals"
                                className="text-sm text-orange-600 hover:text-orange-700 flex items-center gap-1"
                            >
                                {t('dashboard.pending_items.view_all', 'View All')}
                                <ArrowRight className="h-3 w-3" />
                            </Link>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {pendingItems.map((item) => (
                                <div key={`${item.type}-${item.id}`} className="flex items-center justify-between p-3 bg-white rounded-lg border border-orange-200">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-orange-100 rounded-lg">
                                            {item.type === 'approval' && <ListChecks className="h-4 w-4 text-orange-600" />}
                                            {item.type === 'expense' && <DollarSign className="h-4 w-4 text-orange-600" />}
                                            {item.type === 'invoice' && <FileText className="h-4 w-4 text-orange-600" />}
                                        </div>
                                        <div>
                                            <div className="font-medium text-sm text-gray-900">{item.title}</div>
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