import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Search, Loader2, Pencil, Trash2, Eye, Package, AlertTriangle, TrendingUp, DollarSign, BarChart3, Zap, Target, Lightbulb, Image as ImageIcon } from "lucide-react";
import { useState, useEffect } from "react";
import { inventoryApi, InventoryItem, InventoryCategory, InventoryAnalytics, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';
import { BarcodeScanner } from "@/components/inventory/BarcodeScanner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDateTime } from "@/lib/utils";
import { PageHeader } from "@/components/ui/professional-layout";
import { ProfessionalCard, MetricCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";

const Inventory = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [analytics, setAnalytics] = useState<InventoryAnalytics | null>(null);
  const [advancedAnalytics, setAdvancedAnalytics] = useState<any>(null);
  const [salesVelocity, setSalesVelocity] = useState<any>(null);
  const [forecasting, setForecasting] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<number | "all">("all");
  const [itemToDelete, setItemToDelete] = useState<InventoryItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  // Check if user can perform actions (not a viewer)
  const canPerformAction = canPerformActions();

  // Detect user's business type for contextual messaging
  const getUserBusinessType = () => {
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user.business_type || 'service';
      }
    } catch (e) {
      console.error('Error getting business type:', e);
    }
    return 'service';
  };

  const businessType = getUserBusinessType();

  // Get current tenant ID to trigger refetch when organization switches
  const getCurrentTenantId = () => {
    try {
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        return selectedTenantId;
      }
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user?.tenant_id?.toString();
      }
    } catch (e) {
      console.error('Error getting tenant ID:', e);
    }
    return null;
  };

  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

  // Update tenant ID when it changes
  useEffect(() => {
    const updateTenantId = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Inventory: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
        setCurrentTenantId(tenantId);
      }
    };

    updateTenantId();

    // Listen for storage changes
    const handleStorageChange = () => {
      updateTenantId();
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [currentTenantId]);

  // Fetch advanced analytics data
  const fetchAdvancedAnalytics = async () => {
    try {
      setAnalyticsLoading(true);
      const [advancedData, velocityData, forecastData] = await Promise.all([
        inventoryApi.getAdvancedAnalytics(),
        inventoryApi.getSalesVelocity(),
        inventoryApi.getForecasting()
      ]);

      setAdvancedAnalytics(advancedData);
      setSalesVelocity(velocityData);
      setForecasting(forecastData);
    } catch (error) {
      console.error("Failed to fetch advanced analytics:", error);
      // Don't show error toast for analytics as it's secondary
    } finally {
      setAnalyticsLoading(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [itemsData, categoriesData, analyticsData] = await Promise.all([
          inventoryApi.getItems({ limit: 100 }),
          inventoryApi.getCategories(),
          inventoryApi.getAnalytics()
        ]);

        setItems(itemsData.items);
        setCategories(categoriesData);
        setAnalytics(analyticsData);

        // Fetch advanced analytics in background
        fetchAdvancedAnalytics();
      } catch (error) {
        console.error("Failed to fetch inventory data:", error);
        toast.error(getErrorMessage(error, t));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [currentTenantId]);

  const filteredItems = items.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.sku?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory = selectedCategory === "all" || item.category_id === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  const handleDelete = async () => {
    if (!itemToDelete) return;

    setDeleting(true);
    try {
      await inventoryApi.deleteItem(itemToDelete.id);
      setItems(items.filter(i => i.id !== itemToDelete.id));
      toast.success(t('inventory.item_deleted', { name: itemToDelete.name }));
    } catch (error) {
      console.error("Failed to delete item:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setDeleting(false);
      setItemToDelete(null);
    }
  };

  const getStockStatus = (item: InventoryItem) => {
    if (!item.track_stock) return { status: 'not-tracked', label: t('inventory.stock_status.not_tracked', 'Not Tracked') };

    if (item.current_stock <= item.minimum_stock) {
      return { status: 'critical', label: t('inventory.stock_status.low_stock', 'Low Stock'), color: 'destructive' as const };
    } else if (item.current_stock <= item.minimum_stock * 1.5) {
      return { status: 'warning', label: t('inventory.stock_status.low_stock', 'Low Stock'), color: 'secondary' as const };
    } else {
      return { status: 'normal', label: t('inventory.stock_status.in_stock', 'In Stock'), color: 'default' as const };
    }
  };

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('inventory.title', 'Inventory')}
          description={businessType === 'service'
            ? t('inventory.service_description', 'Create a service catalog for your consulting and freelance work')
            : t('inventory.product_description', 'Manage your products and stock levels')
          }
          actions={
            <div className="flex gap-2">
              {canPerformAction && (
                <>
                  <Link to="/inventory/new">
                    <ProfessionalButton className="sm:self-end whitespace-nowrap">
                      <Plus className="mr-2 h-4 w-4" /> {t('inventory.add_item', 'Add Item')}
                    </ProfessionalButton>
                  </Link>
                  <BarcodeScanner
                    onItemFound={(item) => {
                      toast.success(`Found item: ${item.name}`);
                      // Could navigate to item details or add to cart
                    }}
                    autoClose={false}
                  />
                </>
              )}
            </div>
          }
        />

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full tabs-professional">
          <TabsList className="grid w-full grid-cols-4 bg-gradient-to-r from-muted/50 to-muted/30 border border-border/50 rounded-lg p-1">
            <TabsTrigger value="overview" className="flex items-center gap-2 data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">
              <Package className="h-4 w-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="analytics" className="flex items-center gap-2 data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">
              <BarChart3 className="h-4 w-4" />
              Analytics
            </TabsTrigger>
            <TabsTrigger value="forecasting" className="flex items-center gap-2 data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">
              <Target className="h-4 w-4" />
              Forecasting
            </TabsTrigger>
            <TabsTrigger value="insights" className="flex items-center gap-2 data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">
              <Lightbulb className="h-4 w-4" />
              Insights
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            {/* Analytics Cards */}
            {analytics && (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  title={t('inventory.analytics.total_items', 'Total Items')}
                  value={analytics.total_items}
                  icon={Package}
                  description={`${analytics.active_items} ${t('inventory.analytics.active', 'active')}`}
                />

                <MetricCard
                  title={t('inventory.analytics.low_stock_items', 'Low Stock Items')}
                  value={analytics.low_stock_items}
                  icon={AlertTriangle}
                  description={t('inventory.analytics.need_attention', 'Need attention')}
                  variant="warning"
                />

                <MetricCard
                  title={t('inventory.analytics.inventory_value', 'Inventory Value')}
                  value={<CurrencyDisplay amount={analytics.total_value} currency={analytics.currency} /> as any}
                  icon={DollarSign}
                  description={t('inventory.total', 'Total')}
                />

                <MetricCard
                  title={t('inventory.analytics.categories', 'Categories')}
                  value={categories.length}
                  icon={TrendingUp}
                  description={t('inventory.analytics.product_categories', 'Product categories')}
                />
              </div>
            )}

            <ProfessionalCard className="slide-in">
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row justify-between gap-4">
                  <CardTitle>{t('inventory.items_list', 'Inventory Items')}</CardTitle>
                  <div className="flex gap-2">
                    <select
                      className="px-3 py-2 border border-input bg-background rounded-md text-sm"
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value === "all" ? "all" : parseInt(e.target.value))}
                    >
                      <option value="all">{t('inventory.all_categories', 'All Categories')}</option>
                      {categories.map(category => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                    </select>
                    <div className="relative max-w-sm">
                      <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder={t('inventory.search_placeholder', 'Search items...')}
                        className="pl-8"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                        <TableHead>{t('inventory.table.name', 'Name')}</TableHead>
                        <TableHead>{t('inventory.table.sku', 'SKU')}</TableHead>
                        <TableHead>{t('inventory.table.category', 'Category')}</TableHead>
                        <TableHead className="text-right">{t('inventory.table.price', 'Price')}</TableHead>
                        <TableHead className="text-right">{t('inventory.table.stock', 'Stock')}</TableHead>
                        <TableHead>{t('inventory.table.created_date', 'Created')}</TableHead>
                        <TableHead>{t('inventory.table.updated_date', 'Updated')}</TableHead>
                        <TableHead>{t('inventory.table.status', 'Status')}</TableHead>
                        <TableHead className="w-[100px]">{t('inventory.table.actions', 'Actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loading ? (
                        <TableRow>
                          <TableCell colSpan={9} className="h-24 text-center">
                            <div className="flex justify-center items-center">
                              <Loader2 className="h-12 w-12 animate-spin text-primary/60 mr-3" />
                              <span className="text-muted-foreground">{t('inventory.loading', 'Loading inventory...')}</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : filteredItems.length > 0 ? (
                        filteredItems.map((item) => {
                          const stockStatus = getStockStatus(item);
                          return (
                            <TableRow key={item.id} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
                              <TableCell className="font-medium">
                                <div className="flex items-start gap-2">
                                  <div className="flex-1">
                                    <div className="font-medium">{item.name}</div>
                                    {item.description && (
                                      <div className="text-sm text-muted-foreground truncate max-w-xs">
                                        {item.description}
                                      </div>
                                    )}
                                  </div>
                                  {/* Attachment indicator - can be enhanced when API provides attachment counts */}
                                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <ImageIcon className="w-3 h-3" />
                                    {/* Placeholder for attachment count - will be populated when API is enhanced */}
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell>{item.sku || '-'}</TableCell>
                              <TableCell>{item.category?.name || '-'}</TableCell>
                              <TableCell className="text-right font-medium">
                                <CurrencyDisplay amount={item.unit_price} currency={item.currency} />
                              </TableCell>
                              <TableCell className="text-right">
                                {item.track_stock ? (
                                  <span className={item.current_stock <= item.minimum_stock ? 'text-red-600 font-medium' : ''}>
                                    {item.current_stock}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">-</span>
                                )}
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {formatDateTime(item.created_at)}
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {formatDateTime(item.updated_at)}
                              </TableCell>
                              <TableCell>
                                <Badge variant={stockStatus.color || 'default'}>
                                  {stockStatus.label}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <Link to={`/inventory/view/${item.id}`}>
                                    <Button variant="ghost" size="icon" title="View Details">
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                  </Link>
                                  {canPerformAction && (
                                    <>
                                      <Link to={`/inventory/edit/${item.id}`}>
                                        <Button variant="ghost" size="icon" title="Edit Item">
                                          <Pencil className="h-4 w-4" />
                                        </Button>
                                      </Link>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        title="Delete Item"
                                        onClick={() => setItemToDelete(item)}
                                      >
                                        <Trash2 className="h-4 w-4 text-red-500" />
                                      </Button>
                                    </>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })
                      ) : (
                        <TableRow>
                          <TableCell colSpan={9} className="h-auto p-0 border-none">
                            <div className="text-center py-20 bg-gradient-to-br from-muted/5 via-muted/2 to-transparent rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                              <div className="bg-gradient-to-br from-primary/15 to-primary/5 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
                                <Package className="h-8 w-8 text-primary" />
                              </div>
                              <h3 className="text-2xl font-bold mb-2">
                                {businessType === 'service'
                                  ? t('inventory.no_service_items', 'No service items yet')
                                  : t('inventory.no_product_items', 'No inventory items yet')
                                }
                              </h3>
                              <p className="text-muted-foreground max-w-sm mx-auto mb-6">
                                {businessType === 'service'
                                  ? t('inventory.service_description_empty', 'Create your service catalog to get started. Services can be added to invoices easily.')
                                  : t('inventory.product_description_empty', 'Add your products to track stock levels and add them to invoices.')
                                }
                              </p>
                              {canPerformAction && (
                                <Link to="/inventory/new">
                                  <ProfessionalButton>
                                    <Plus className="mr-2 h-4 w-4" /> {t('inventory.add_item', 'Add Item')}
                                  </ProfessionalButton>
                                </Link>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </ProfessionalCard>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-6">
            <div className="flex items-center justify-between bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
              <div>
                <h2 className="text-4xl font-bold mb-2">Advanced Analytics</h2>
                <p className="text-muted-foreground">Detailed insights into your inventory performance</p>
              </div>
              <ProfessionalButton onClick={fetchAdvancedAnalytics} disabled={analyticsLoading}>
                {analyticsLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <BarChart3 className="h-4 w-4 mr-2" />
                )}
                Refresh Analytics
              </ProfessionalButton>
            </div>

            {advancedAnalytics && (
              <>
                {/* Key Metrics Cards */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <MetricCard
                    title="Revenue Growth"
                    value={`${advancedAnalytics.key_metrics.revenue_growth_percent >= 0 ? '+' : ''}${advancedAnalytics.key_metrics.revenue_growth_percent.toFixed(1)}%`}
                    icon={TrendingUp}
                    description="vs last period"
                    variant={advancedAnalytics.key_metrics.revenue_growth_percent >= 0 ? 'success' : 'danger'}
                  />

                  <MetricCard
                    title="Avg Daily Revenue"
                    value={<CurrencyDisplay amount={advancedAnalytics.key_metrics.avg_daily_revenue} currency={analytics.currency} /> as any}
                    icon={DollarSign}
                    description="per day average"
                  />

                  <MetricCard
                    title="Best Category"
                    value={advancedAnalytics.key_metrics.best_performing_category || 'N/A'}
                    icon={BarChart3}
                    description="top performer"
                  />

                  <MetricCard
                    title="Total Items Sold"
                    value={advancedAnalytics.key_metrics.total_items_sold}
                    icon={Package}
                    description="unique items"
                  />
                </div>

                {/* Top Performing Items */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>Top Performing Items</CardTitle>
                    <p className="text-sm text-muted-foreground">Items with highest revenue in the selected period</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {advancedAnalytics.top_performing_items.slice(0, 10).map((item: any, index: number) => (
                        <div key={item.id} className="flex items-center justify-between p-4 border rounded-lg">
                          <div className="flex items-center gap-4">
                            <div className="flex items-center justify-center w-8 h-8 bg-primary/10 rounded-full">
                              <span className="text-sm font-medium">#{index + 1}</span>
                            </div>
                            <div>
                              <div className="font-medium">{item.name}</div>
                              <div className="text-sm text-muted-foreground">
                                {item.total_sold} sold • {item.invoice_count} invoices
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold"><CurrencyDisplay amount={item.total_revenue} currency={analytics.currency} /></div>
                            <div className="text-sm text-muted-foreground">
                              <CurrencyDisplay amount={item.total_revenue / item.total_sold} currency={analytics.currency} /> avg
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </ProfessionalCard>

                {/* Category Performance */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>Category Performance</CardTitle>
                    <p className="text-sm text-muted-foreground">Revenue breakdown by category</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {advancedAnalytics.category_performance.map((category: any) => (
                        <div key={category.category} className="flex items-center justify-between p-4 border rounded-lg">
                          <div>
                            <div className="font-medium">{category.category}</div>
                            <div className="text-sm text-muted-foreground">
                              {category.item_count} items • {category.total_sold} sold
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold"><CurrencyDisplay amount={category.total_revenue} currency={analytics.currency} /></div>
                            <div className="text-sm text-muted-foreground">
                              <CurrencyDisplay amount={category.total_revenue / category.total_sold} currency={analytics.currency} /> avg price
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </>
            )}
          </TabsContent>

          <TabsContent value="forecasting" className="space-y-6">
            <div className="flex items-center justify-between bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
              <div>
                <h2 className="text-4xl font-bold mb-2">Inventory Forecasting</h2>
                <p className="text-muted-foreground">AI-powered demand forecasting and stock optimization</p>
              </div>
              <ProfessionalButton onClick={fetchAdvancedAnalytics} disabled={analyticsLoading}>
                {analyticsLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Target className="h-4 w-4 mr-2" />
                )}
                Refresh Forecast
              </ProfessionalButton>
            </div>

            {forecasting && (
              <>
                {/* Forecast Summary Cards */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <MetricCard
                    title="Items Forecasted"
                    value={forecasting.summary.total_items_forecasted}
                    icon={BarChart3}
                    description="with sufficient data"
                  />

                  <MetricCard
                    title="High Confidence"
                    value={forecasting.summary.high_confidence_forecasts}
                    icon={Target}
                    description=">80% accuracy"
                    variant="success"
                  />

                  <MetricCard
                    title="Total Demand"
                    value={forecasting.summary.total_forecasted_demand.toFixed(0)}
                    icon={Zap}
                    description="next 90 days"
                  />

                  <MetricCard
                    title="Seasonal Items"
                    value={forecasting.summary.seasonal_items}
                    icon={TrendingUp}
                    description="detected patterns"
                  />
                </div>

                {/* Forecast Items */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>Demand Forecasts</CardTitle>
                    <p className="text-sm text-muted-foreground">AI-powered predictions for the next 90 days</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {forecasting.forecasts.slice(0, 10).map((item: any) => (
                        <div key={item.item_id} className="flex items-center justify-between p-4 border rounded-lg">
                          <div className="flex items-center gap-4">
                            <div className={`w-3 h-3 rounded-full ${item.forecast_confidence_percent > 80 ? 'bg-green-500' :
                              item.forecast_confidence_percent > 60 ? 'bg-yellow-500' : 'bg-red-500'
                              }`} />
                            <div>
                              <div className="font-medium">{item.item_name}</div>
                              <div className="text-sm text-muted-foreground">
                                {item.historical_days} days of data • {item.avg_daily_sales.toFixed(1)} avg daily
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold">{item.forecast_total.toFixed(0)} units</div>
                            <div className="text-sm text-muted-foreground">
                              {item.forecast_confidence_percent.toFixed(0)}% confidence
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </>
            )}
          </TabsContent>

          <TabsContent value="insights" className="space-y-6">
            <div className="flex items-center justify-between bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
              <div>
                <h2 className="text-4xl font-bold mb-2">AI Insights</h2>
                <p className="text-muted-foreground">Automated analysis and recommendations</p>
              </div>
              <ProfessionalButton onClick={fetchAdvancedAnalytics} disabled={analyticsLoading}>
                {analyticsLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Lightbulb className="h-4 w-4 mr-2" />
                )}
                Generate Insights
              </ProfessionalButton>
            </div>

            {advancedAnalytics && advancedAnalytics.insights && (
              <div className="grid gap-4">
                {advancedAnalytics.insights.map((insight: any, index: number) => (
                  <ProfessionalCard key={index} className={`border-l-4 ${insight.type === 'positive' ? 'border-l-green-500' :
                    insight.type === 'warning' ? 'border-l-yellow-500' :
                      insight.type === 'info' ? 'border-l-blue-500' : 'border-l-gray-500'
                    }`}>
                    <CardContent className="pt-6">
                      <div className="flex items-start gap-4">
                        <div className={`p-2 rounded-full ${insight.type === 'positive' ? 'bg-green-100 text-green-600' :
                          insight.type === 'warning' ? 'bg-yellow-100 text-yellow-600' :
                            insight.type === 'info' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
                          }`}>
                          {insight.type === 'positive' ? '📈' :
                            insight.type === 'warning' ? '⚠️' :
                              insight.type === 'info' ? 'ℹ️' : '💡'}
                        </div>
                        <div className="flex-1">
                          <h3 className="font-semibold mb-2">{insight.title}</h3>
                          <p className="text-muted-foreground">{insight.description}</p>
                        </div>
                      </div>
                    </CardContent>
                  </ProfessionalCard>
                ))}
              </div>
            )}

            {salesVelocity && (
              <>
                {/* Sales Velocity Summary */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>Sales Velocity Overview</CardTitle>
                    <p className="text-sm text-muted-foreground">Stock movement analysis and recommendations</p>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600">
                          {salesVelocity.summary.high_velocity_items}
                        </div>
                        <div className="text-sm text-muted-foreground">High Velocity Items</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-red-600">
                          {salesVelocity.summary.out_of_stock_risk}
                        </div>
                        <div className="text-sm text-muted-foreground">Out of Stock Risk</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-orange-600">
                          {salesVelocity.summary.overstocked_items}
                        </div>
                        <div className="text-sm text-muted-foreground">Overstocked Items</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">
                          {salesVelocity.summary.avg_daily_sales_rate.toFixed(1)}
                        </div>
                        <div className="text-sm text-muted-foreground">Avg Daily Sales Rate</div>
                      </div>
                    </div>
                  </CardContent>
                </ProfessionalCard>

                {/* Stock Status Recommendations */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>Stock Optimization Recommendations</CardTitle>
                    <p className="text-sm text-muted-foreground">Items requiring attention based on sales velocity</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {salesVelocity.items.filter((item: any) =>
                        item.stock_status === 'critical' || item.stock_status === 'overstocked'
                      ).slice(0, 5).map((item: any) => (
                        <div key={item.item_id} className="flex items-center justify-between p-4 border rounded-lg">
                          <div>
                            <div className="font-medium">{item.item_name}</div>
                            <div className="text-sm text-muted-foreground">
                              Current: {item.current_stock} • Recommended: {item.recommended_stock_level.toFixed(0)}
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge variant={
                              item.stock_status === 'critical' ? 'destructive' :
                                item.stock_status === 'overstocked' ? 'secondary' : 'default'
                            }>
                              {item.stock_status}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <Dialog open={!!itemToDelete} onOpenChange={() => setItemToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('inventory.delete_item', 'Delete Item')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>{t('inventory.delete_confirm', {
              name: itemToDelete?.name,
              defaultValue: 'Are you sure you want to delete "{{name}}"? This action cannot be undone.'
            })}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setItemToDelete(null)}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('common.delete', 'Delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default Inventory;
