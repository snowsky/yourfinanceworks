import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, Search, Loader2, Pencil, Trash2, Package, AlertTriangle, TrendingUp, DollarSign } from "lucide-react";
import { useState, useEffect } from "react";
import { inventoryApi, InventoryItem, InventoryCategory, InventoryAnalytics, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';

const Inventory = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [analytics, setAnalytics] = useState<InventoryAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<number | "all">("all");
  const [itemToDelete, setItemToDelete] = useState<InventoryItem | null>(null);
  const [deleting, setDeleting] = useState(false);

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
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{t('inventory.title', 'Inventory')}</h1>
            <p className="text-muted-foreground">
              {businessType === 'service'
                ? t('inventory.service_description', 'Create a service catalog for your consulting and freelance work')
                : t('inventory.product_description', 'Manage your products and stock levels')
              }
            </p>
          </div>
          {canPerformAction && (
            <Link to="/inventory/new">
              <Button className="sm:self-end whitespace-nowrap">
                <Plus className="mr-2 h-4 w-4" /> {t('inventory.add_item', 'Add Item')}
              </Button>
            </Link>
          )}
        </div>

        {/* Analytics Cards */}
        {analytics && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('inventory.analytics.total_items', 'Total Items')}</CardTitle>
                <Package className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{analytics.total_items}</div>
                <p className="text-xs text-muted-foreground">
                  {analytics.active_items} {t('inventory.analytics.active', 'active')}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('inventory.analytics.low_stock_items', 'Low Stock Items')}</CardTitle>
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-600">{analytics.low_stock_items}</div>
                <p className="text-xs text-muted-foreground">
                  {t('inventory.analytics.need_attention', 'Need attention')}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('inventory.analytics.inventory_value', 'Inventory Value')}</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">${analytics.total_value.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">
                  {analytics.currency}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{t('inventory.analytics.categories', 'Categories')}</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{categories.length}</div>
                <p className="text-xs text-muted-foreground">
                  {t('inventory.analytics.product_categories', 'Product categories')}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        <Card className="slide-in">
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
                  <TableRow>
                    <TableHead>{t('inventory.table.name', 'Name')}</TableHead>
                    <TableHead>{t('inventory.table.sku', 'SKU')}</TableHead>
                    <TableHead>{t('inventory.table.category', 'Category')}</TableHead>
                    <TableHead className="text-right">{t('inventory.table.price', 'Price')}</TableHead>
                    <TableHead className="text-right">{t('inventory.table.stock', 'Stock')}</TableHead>
                    <TableHead>{t('inventory.table.status', 'Status')}</TableHead>
                    <TableHead className="w-[100px]">{t('inventory.table.actions', 'Actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('inventory.loading', 'Loading inventory...')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : filteredItems.length > 0 ? (
                    filteredItems.map((item) => {
                      const stockStatus = getStockStatus(item);
                      return (
                        <TableRow key={item.id} className="hover:bg-muted/50">
                          <TableCell className="font-medium">
                            <div>
                              <div className="font-medium">{item.name}</div>
                              {item.description && (
                                <div className="text-sm text-muted-foreground truncate max-w-xs">
                                  {item.description}
                                </div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>{item.sku || '-'}</TableCell>
                          <TableCell>{item.category?.name || '-'}</TableCell>
                          <TableCell className="text-right font-medium">
                            ${item.unit_price.toFixed(2)}
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
                          <TableCell>
                            <Badge variant={stockStatus.color || 'default'}>
                              {stockStatus.label}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {canPerformAction && (
                                <>
                                  <Link to={`/inventory/edit/${item.id}`}>
                                    <Button variant="ghost" size="icon">
                                      <Pencil className="h-4 w-4" />
                                    </Button>
                                  </Link>
                                  <Button
                                    variant="ghost"
                                    size="icon"
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
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="space-y-2">
                          <p className="text-muted-foreground">
                            {businessType === 'service'
                              ? t('inventory.no_service_items', 'No service items yet. Create your service catalog to get started.')
                              : t('inventory.no_product_items', 'No inventory items found. Add your first product to get started.')
                            }
                          </p>
                          {canPerformAction && (
                            <Link to="/inventory/new">
                              <Button variant="outline" size="sm">
                                <Plus className="mr-2 h-4 w-4" />
                                {businessType === 'service'
                                  ? t('inventory.add_first_service', 'Add Your First Service')
                                  : t('inventory.add_first_product', 'Add Your First Product')
                                }
                              </Button>
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
        </Card>
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
    </AppLayout>
  );
};

export default Inventory;
