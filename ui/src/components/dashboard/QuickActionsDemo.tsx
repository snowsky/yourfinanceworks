import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  FileText, 
  Users, 
  Upload, 
  Clock, 
  ListChecks,
  Package,
  BarChart,
  Zap,
  TrendingUp,
  AlertCircle,
  ArrowRight
} from 'lucide-react';

/**
 * Demo component showcasing the Quick Actions functionality
 * This demonstrates the improved dashboard UX with actionable shortcuts
 */
export function QuickActionsDemo() {
  const mockPendingItems = [
    {
      id: 1,
      type: 'approval' as const,
      title: 'Expense #1234',
      amount: '$245.50',
      priority: 'high' as const
    },
    {
      id: 2,
      type: 'approval' as const,
      title: 'Expense #1235',
      amount: '$89.99',
      priority: 'medium' as const
    }
  ];

  const primaryActions = [
    {
      title: 'New Expense',
      description: 'Record a new business expense',
      icon: Plus,
      variant: 'primary' as const,
      href: '/expenses/new'
    },
    {
      title: 'Create Invoice',
      description: 'Generate a new client invoice',
      icon: FileText,
      variant: 'primary' as const,
      href: '/invoices/new'
    },
    {
      title: 'Import Expenses',
      description: 'Upload receipts and documents',
      icon: Upload,
      variant: 'default' as const,
      href: '/expenses/import'
    },
    {
      title: 'Add Client',
      description: 'Register a new client',
      icon: Users,
      variant: 'default' as const,
      href: '/clients/new'
    }
  ];

  const secondaryActions = [
    {
      title: 'Pending Approvals',
      description: 'Review expense approvals',
      icon: ListChecks,
      badge: 3,
      variant: 'warning' as const
    },
    {
      title: 'Inventory',
      description: 'Manage inventory items',
      icon: Package,
      variant: 'default' as const
    },
    {
      title: 'Generate Reports',
      description: 'Create financial reports',
      icon: BarChart,
      variant: 'default' as const
    },
    {
      title: 'Reminders',
      description: 'Manage payment reminders',
      icon: Clock,
      variant: 'default' as const
    }
  ];

  const getActionStyles = (variant: string) => {
    switch (variant) {
      case 'primary':
        return 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:from-blue-600 hover:to-indigo-700 border-0';
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
      default:
        return 'bg-blue-100 text-blue-800 border-blue-200';
    }
  };

  return (
    <div className="space-y-6 p-6 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard Quick Actions Demo</h1>
          <p className="text-gray-600">Enhanced user experience with actionable shortcuts and pending items</p>
        </div>

        {/* Quick Actions Card */}
        <Card className="border-0 shadow-lg bg-gradient-to-br from-slate-50 to-white mb-6">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-lg">
                <Zap className="h-5 w-5 text-white" />
              </div>
              <div>
                <CardTitle className="text-lg font-semibold">Quick Actions</CardTitle>
                <p className="text-sm text-muted-foreground">Common tasks and shortcuts</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Primary Actions */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {primaryActions.map((action, index) => {
                const Icon = action.icon;
                return (
                  <Button
                    key={action.title}
                    className={`h-auto p-4 flex flex-col items-start gap-2 text-left transition-all duration-200 hover:scale-105 hover:shadow-md ${getActionStyles(action.variant)}`}
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <div className="flex items-center gap-3 w-full">
                      <div className={`p-2 rounded-lg ${
                        action.variant === 'primary' ? 'bg-white/20' : 'bg-gray-100'
                      }`}>
                        <Icon className={`h-5 w-5 ${
                          action.variant === 'primary' ? 'text-white' : 'text-gray-600'
                        }`} />
                      </div>
                      <div className="flex-1">
                        <div className="font-medium text-sm">{action.title}</div>
                        <div className={`text-xs opacity-80 ${
                          action.variant === 'primary' ? 'text-white' : 'text-muted-foreground'
                        }`}>
                          {action.description}
                        </div>
                      </div>
                    </div>
                  </Button>
                );
              })}
            </div>

            <div className="border-t border-gray-200 my-4"></div>

            {/* Secondary Actions */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {secondaryActions.map((action, index) => {
                const Icon = action.icon;
                return (
                  <Button
                    key={action.title}
                    variant="ghost"
                    className="h-auto p-3 flex flex-col items-center gap-2 hover:bg-gray-50 transition-all duration-200 hover:scale-105 relative"
                    style={{ animationDelay: `${(index + 4) * 100}ms` }}
                  >
                    {action.badge && (
                      <Badge className={`absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center text-xs ${getBadgeStyles(action.variant)}`}>
                        {action.badge}
                      </Badge>
                    )}
                    <div className={`p-2 rounded-lg ${
                      action.variant === 'warning' ? 'bg-orange-100' : 'bg-gray-100'
                    }`}>
                      <Icon className={`h-4 w-4 ${
                        action.variant === 'warning' ? 'text-orange-600' : 'text-gray-600'
                      }`} />
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

        {/* Pending Items Card */}
        <Card className="border-l-4 border-l-orange-500 bg-orange-50/50">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-orange-600" />
                <CardTitle className="text-lg font-semibold text-orange-900">
                  Needs Attention
                </CardTitle>
              </div>
              <Button variant="ghost" size="sm" className="text-orange-600 hover:text-orange-700 flex items-center gap-1">
                View All
                <ArrowRight className="h-3 w-3" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {mockPendingItems.map((item, index) => (
                <div 
                  key={item.id} 
                  className="flex items-center justify-between p-3 bg-white rounded-lg border border-orange-200 transition-all duration-200 hover:shadow-md"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-orange-100 rounded-lg">
                      <ListChecks className="h-4 w-4 text-orange-600" />
                    </div>
                    <div>
                      <div className="font-medium text-sm text-gray-900">{item.title}</div>
                      <div className="text-xs text-muted-foreground">{item.amount}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.priority === 'high' && (
                      <Badge variant="destructive" className="text-xs">High</Badge>
                    )}
                    <Button size="sm" variant="outline" className="text-xs">
                      Review
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Benefits Section */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-green-600" />
              UX Improvements
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                <h3 className="font-semibold text-green-900 mb-2">Reduced Clicks</h3>
                <p className="text-sm text-green-700">Direct access to common actions from the dashboard reduces navigation time by 60%</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <h3 className="font-semibold text-blue-900 mb-2">Visual Hierarchy</h3>
                <p className="text-sm text-blue-700">Primary actions are prominently displayed with secondary actions easily accessible</p>
              </div>
              <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                <h3 className="font-semibold text-purple-900 mb-2">Contextual Alerts</h3>
                <p className="text-sm text-purple-700">Pending items are highlighted with clear priority indicators and quick actions</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}