import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Save, Loader2 } from "lucide-react";
import { inventoryApi, InventoryItem, InventoryCategory, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from 'react-i18next';
import { InventoryItemLinkedInvoices } from "./InventoryItemLinkedInvoices";

interface InventoryItemFormProps {
  isEdit?: boolean;
}

const InventoryItemForm = ({ isEdit = false }: InventoryItemFormProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  // Detect user's business type to set appropriate defaults
  const getUserBusinessType = () => {
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user.business_type || 'service'; // Default to service for existing users
      }
    } catch (e) {
      console.error('Error getting business type:', e);
    }
    return 'service'; // Default fallback
  };

  const businessType = getUserBusinessType();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    sku: '',
    category_id: '',
    unit_price: '',
    cost_price: '',
    currency: 'USD',
    track_stock: true, // Enable stock tracking by default
    current_stock: '',
    minimum_stock: '',
    unit_of_measure: businessType === 'service' ? 'hours' : 'each', // Services often measured in hours
    item_type: businessType === 'service' ? 'service' : 'product', // Default based on business type
    is_active: true,
    unlimited_stock: businessType === 'service' ? true : false // Services default to unlimited
  });

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const categoriesData = await inventoryApi.getCategories();
        setCategories(categoriesData);

        if (isEdit && id) {
          const itemData = await inventoryApi.getItem(parseInt(id));
          // Check if stock is unlimited (very high number for services)
          const isUnlimited = !itemData.track_stock && itemData.current_stock >= 999999;

          setFormData({
            name: itemData.name,
            description: itemData.description || '',
            sku: itemData.sku || '',
            category_id: itemData.category_id?.toString() || '',
            unit_price: itemData.unit_price.toString(),
            cost_price: itemData.cost_price?.toString() || '',
            currency: itemData.currency,
            track_stock: itemData.track_stock,
            current_stock: isUnlimited ? '' : itemData.current_stock.toString(),
            minimum_stock: itemData.minimum_stock.toString(),
            unit_of_measure: itemData.unit_of_measure,
            item_type: itemData.item_type,
            is_active: itemData.is_active,
            unlimited_stock: isUnlimited
          });
        }
      } catch (error) {
        console.error("Failed to fetch data:", error);
        toast.error(getErrorMessage(error, t));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [isEdit, id]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => {
      const newData = { ...prev, [field]: value };

      // Handle special cases
      if (field === 'item_type') {
        // Auto-adjust defaults based on item type
        if (value === 'service' && !isEdit) {
          newData.track_stock = true;  // Enable stock tracking for services
          newData.unlimited_stock = true;  // But default to unlimited
          newData.unit_of_measure = 'hours';
        } else if (value === 'product' && !isEdit) {
          newData.track_stock = true;
          newData.unlimited_stock = false;
          newData.unit_of_measure = 'each';
        }
      }

      if (field === 'track_stock') {
        // When enabling stock tracking for services, offer unlimited option
        if (value && newData.item_type === 'service') {
          newData.unlimited_stock = true;
        } else if (!value) {
          newData.unlimited_stock = false;
        }
      }

      if (field === 'unlimited_stock') {
        // When unlimited is toggled, update current_stock accordingly
        if (value) {
          newData.current_stock = '';
          newData.minimum_stock = '';
        }
      }

      return newData;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Basic validation
    if (!formData.name.trim()) {
      toast.error(t('inventory.validation.name_required', 'Item name is required'));
      return;
    }

    if (!formData.unit_price || parseFloat(formData.unit_price) <= 0) {
      toast.error(t('inventory.validation.price_required', 'Valid unit price is required'));
      return;
    }

    setSaving(true);
    try {
      // Handle stock values based on type and unlimited setting
      let current_stock: number;
      let minimum_stock: number;

      if (formData.track_stock) {
        // Normal stock tracking
        current_stock = parseFloat(formData.current_stock || '0');
        minimum_stock = parseFloat(formData.minimum_stock || '0');
      } else if (formData.unlimited_stock && formData.item_type === 'service') {
        // Unlimited stock for services
        current_stock = 999999;
        minimum_stock = 0;
      } else {
        // No stock tracking
        current_stock = 0;
        minimum_stock = 0;
      }

      const itemData = {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        sku: formData.sku.trim() || undefined,
        category_id: formData.category_id ? parseInt(formData.category_id) : undefined,
        unit_price: parseFloat(formData.unit_price),
        cost_price: formData.cost_price ? parseFloat(formData.cost_price) : undefined,
        currency: formData.currency,
        track_stock: formData.track_stock,
        current_stock: current_stock,
        minimum_stock: minimum_stock,
        unit_of_measure: formData.unit_of_measure,
        item_type: formData.item_type,
        is_active: formData.is_active
      };

      if (isEdit && id) {
        await inventoryApi.updateItem(parseInt(id), itemData);
        toast.success(t('inventory.item_updated', 'Item updated successfully'));
      } else {
        await inventoryApi.createItem(itemData);
        toast.success(t('inventory.item_created', 'Item created successfully'));
      }

      navigate('/inventory');
    } catch (error) {
      console.error("Failed to save item:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex justify-center items-center h-64">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/inventory')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('common.back', 'Back')}
          </Button>
          <div>
            <h1 className="text-3xl font-bold">
              {isEdit ? t('inventory.edit_item', 'Edit Item') : t('inventory.new_item', 'New Item')}
            </h1>
            <p className="text-muted-foreground">
              {isEdit
                ? t('inventory.edit_description', 'Update item details and stock information')
                : t('inventory.new_description', 'Add a new item to your inventory')
              }
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('inventory.basic_info', 'Basic Information')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">{t('inventory.name', 'Name')} *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder={t('inventory.name_placeholder', 'Enter item name')}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sku">{t('inventory.sku', 'SKU')}</Label>
                  <Input
                    id="sku"
                    value={formData.sku}
                    onChange={(e) => handleInputChange('sku', e.target.value)}
                    placeholder={t('inventory.sku_placeholder', 'Enter SKU')}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">{t('inventory.description', 'Description')}</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  placeholder={t('inventory.description_placeholder', 'Enter item description')}
                  rows={3}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="category">{t('inventory.category', 'Category')}</Label>
                  <Select
                    value={formData.category_id || "none"}
                    onValueChange={(value) => handleInputChange('category_id', value === "none" ? "" : value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('inventory.select_category', 'Select category')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">{t('inventory.no_category', 'No category')}</SelectItem>
                      {categories.map(category => (
                        <SelectItem key={category.id} value={category.id.toString()}>
                          {category.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="item_type">{t('inventory.item_type', 'Item Type')}</Label>
                  <Select
                    value={formData.item_type}
                    onValueChange={(value) => handleInputChange('item_type', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="service">
                        {t('inventory.service', 'Service')}
                        {businessType === 'service' && (
                          <span className="text-sm text-muted-foreground ml-2">
                            ({t('inventory.recommended', 'recommended')})
                          </span>
                        )}
                      </SelectItem>
                      <SelectItem value="product">{t('inventory.product', 'Product')}</SelectItem>
                      <SelectItem value="material">{t('inventory.material', 'Material')}</SelectItem>
                    </SelectContent>
                  </Select>
                  {businessType === 'service' && (
                    <p className="text-xs text-muted-foreground">
                      {t('inventory.service_type_help', 'Services don\'t require stock tracking and are perfect for consultants and freelancers')}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('inventory.pricing', 'Pricing')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="unit_price">{t('inventory.unit_price', 'Unit Price')} *</Label>
                  <Input
                    id="unit_price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={formData.unit_price}
                    onChange={(e) => handleInputChange('unit_price', e.target.value)}
                    placeholder="0.00"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cost_price">{t('inventory.cost_price', 'Cost Price')}</Label>
                  <Input
                    id="cost_price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={formData.cost_price}
                    onChange={(e) => handleInputChange('cost_price', e.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="currency">{t('inventory.currency', 'Currency')}</Label>
                  <Select
                    value={formData.currency}
                    onValueChange={(value) => handleInputChange('currency', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                      <SelectItem value="GBP">GBP</SelectItem>
                      <SelectItem value="CAD">CAD</SelectItem>
                      <SelectItem value="BRL">BRL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('inventory.stock_management', 'Stock Management')}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {businessType === 'service'
                  ? t('inventory.service_stock_help', 'Services typically don\'t require stock tracking')
                  : t('inventory.product_stock_help', 'Track inventory levels and get low stock alerts')
                }
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="track_stock"
                    checked={formData.track_stock}
                    onCheckedChange={(checked) => handleInputChange('track_stock', checked)}
                  />
                  <Label htmlFor="track_stock">
                    {t('inventory.track_stock', 'Track stock levels')}
                    {businessType === 'service' && (
                      <span className="text-sm text-muted-foreground ml-2">
                        ({t('inventory.optional_for_services', 'optional for services')})
                      </span>
                    )}
                  </Label>
                </div>

              </div>

              {formData.track_stock && (
                <div className="space-y-4">
                  {/* Unlimited Stock Option for Services */}
                  {formData.item_type === 'service' && (
                    <div className="p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-800">
                      <div className="flex items-center space-x-2">
                        <Switch
                          id="unlimited_stock"
                          checked={formData.unlimited_stock}
                          onCheckedChange={(checked) => handleInputChange('unlimited_stock', checked)}
                        />
                        <Label htmlFor="unlimited_stock" className="font-medium">
                          {t('inventory.unlimited_stock', 'Unlimited Stock')}
                        </Label>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {t('inventory.unlimited_stock_help',
                          'Perfect for services like consulting - never runs out and no stock management needed')}
                      </p>
                      {formData.unlimited_stock && (
                        <div className="mt-2 text-sm text-green-600 dark:text-green-400 flex items-center">
                          <span>✓ Available: Unlimited</span>
                        </div>
                      )}
                    </div>
                  )}

                  {!formData.unlimited_stock && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="current_stock">{t('inventory.current_stock', 'Current Stock')}</Label>
                        <Input
                          id="current_stock"
                          type="number"
                          step="0.01"
                          min="0"
                          value={formData.current_stock}
                          onChange={(e) => handleInputChange('current_stock', e.target.value)}
                          placeholder="0"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="minimum_stock">{t('inventory.minimum_stock', 'Minimum Stock')}</Label>
                        <Input
                          id="minimum_stock"
                          type="number"
                          step="0.01"
                          min="0"
                          value={formData.minimum_stock}
                          onChange={(e) => handleInputChange('minimum_stock', e.target.value)}
                          placeholder="0"
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="unit_of_measure">{t('inventory.unit_of_measure', 'Unit of Measure')}</Label>
                    <Select
                      value={formData.unit_of_measure}
                      onValueChange={(value) => handleInputChange('unit_of_measure', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    <SelectContent>
                      {/* Service-oriented units */}
                      <SelectItem value="hours">{t('inventory.hours', 'Hours')}</SelectItem>
                      <SelectItem value="days">{t('inventory.days', 'Days')}</SelectItem>
                      <SelectItem value="sessions">{t('inventory.sessions', 'Sessions')}</SelectItem>
                      <SelectItem value="consultations">{t('inventory.consultations', 'Consultations')}</SelectItem>

                      {/* Product-oriented units */}
                      <SelectItem value="each">{t('inventory.each', 'Each')}</SelectItem>
                      <SelectItem value="kg">{t('inventory.kg', 'Kilogram')}</SelectItem>
                      <SelectItem value="lb">{t('inventory.lb', 'Pound')}</SelectItem>
                      <SelectItem value="liter">{t('inventory.liter', 'Liter')}</SelectItem>
                      <SelectItem value="meter">{t('inventory.meter', 'Meter')}</SelectItem>
                      <SelectItem value="box">{t('inventory.box', 'Box')}</SelectItem>
                      <SelectItem value="pack">{t('inventory.pack', 'Pack')}</SelectItem>
                    </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              <div className="flex items-center space-x-2">
                <Switch
                  id="is_active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => handleInputChange('is_active', checked)}
                />
                <Label htmlFor="is_active">{t('inventory.is_active', 'Item is active')}</Label>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end gap-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/inventory')}
              disabled={saving}
            >
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Save className="mr-2 h-4 w-4" />
              {saving
                ? t('common.saving', 'Saving...')
                : t('common.save', 'Save')
              }
            </Button>
          </div>
        </form>

        {/* Linked Invoices and Stock Movements - Only show for existing items */}
        {isEdit && id && (
          <InventoryItemLinkedInvoices
            itemId={parseInt(id)}
            itemName={formData.name || 'this item'}
          />
        )}
      </div>
    </AppLayout>
  );
};

export default InventoryItemForm;
