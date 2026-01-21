import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Save, Loader2, Package, FileText } from "lucide-react";
import { inventoryApi, InventoryItem, InventoryCategory, getErrorMessage, apiRequest } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from 'react-i18next';
import { CurrencySelector } from "@/components/ui/currency-selector";
import { AttachmentUpload } from "./AttachmentUpload";
import { AttachmentGallery, Attachment } from "./AttachmentGallery";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { PageHeader } from "@/components/ui/professional-layout";

interface InventoryItemFormProps {
  isEdit?: boolean;
}

const InventoryItemForm = ({ isEdit = false }: InventoryItemFormProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);

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

  // Fetch categories with React Query for better caching
  const { data: categories = [] } = useQuery({
    queryKey: ['inventory-categories'],
    queryFn: () => inventoryApi.getCategories(),
    staleTime: 1000 * 60 * 30, // 30 minutes cache
    gcTime: 1000 * 60 * 60, // 1 hour garbage collection
  });

  // Load attachments for the current item
  const loadAttachments = async (itemId: number) => {
    try {
      setAttachmentsLoading(true);
      const data = await apiRequest<Attachment[]>(`/inventory/${itemId}/attachments`);
      setAttachments(data);
    } catch (error) {
      console.error('Failed to load attachments:', error);
    } finally {
      setAttachmentsLoading(false);
    }
  };

  // Handle successful attachment uploads
  const handleAttachmentUpload = (uploadedAttachments: any[]) => {
    // Refresh the attachments list
    if (id) {
      loadAttachments(parseInt(id));
    }
    toast.success(`Successfully uploaded ${uploadedAttachments.length} attachment(s)`);
  };

  // Handle attachment upload errors
  const handleAttachmentUploadError = (error: string) => {
    toast.error(`Upload error: ${error}`);
  };

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

          // Load attachments for this item
          await loadAttachments(parseInt(id));
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

      if (formData.unlimited_stock) {
        // Unlimited stock - set very high number and disable tracking
        current_stock = 999999;
        minimum_stock = 0;
      } else if (formData.track_stock) {
        // Normal stock tracking
        current_stock = parseFloat(formData.current_stock || '0');
        minimum_stock = parseFloat(formData.minimum_stock || '0');
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
        track_stock: formData.unlimited_stock ? false : formData.track_stock,
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
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full space-y-6 fade-in">
      <PageHeader
        title={isEdit ? t('inventory.edit_item', 'Edit Item') : t('inventory.new_item', 'New Item')}
        description={isEdit
          ? t('inventory.edit_description', 'Update item details and stock information')
          : t('inventory.new_description', 'Add a new item to your inventory')
        }
        breadcrumbs={[
          { label: t('inventory.title', 'Inventory'), href: '/inventory' },
          { label: isEdit ? t('common.edit', 'Edit') : t('common.new', 'New') }
        ]}
      />

      <Tabs defaultValue="details" className="w-full tabs-professional">
        <TabsList className="grid w-full grid-cols-3 bg-gradient-to-r from-muted/50 to-muted/30 border border-border/50 rounded-lg p-1">
          <TabsTrigger value="details" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">{t('inventory.item_details', 'Item Details')}</TabsTrigger>
          <TabsTrigger value="attachments" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">
            {t('inventory.attachments', 'Attachments')}
            {attachments.length > 0 && (
              <span className="ml-2 bg-primary text-primary-foreground text-xs px-2 py-1 rounded-full">
                {attachments.length}
              </span>
            )}
          </TabsTrigger>
          {isEdit && id && (
            <TabsTrigger value="activity" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">
              {t('inventory.activity', 'Activity')}
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="details" className="space-y-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <ProfessionalCard>
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
            </ProfessionalCard>

            <ProfessionalCard>
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
                    <Label>{t('inventory.currency', 'Currency')}</Label>
                    <CurrencySelector
                      value={formData.currency}
                      onValueChange={(value) => handleInputChange('currency', value)}
                      placeholder={t('inventory.select_currency', 'Select currency')}
                    />
                  </div>
                </div>
              </CardContent>
            </ProfessionalCard>

            <ProfessionalCard>
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
            </ProfessionalCard>

            <div className="flex justify-end gap-4 items-center">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/inventory')}
                disabled={saving}
              >
                {t('common.cancel', 'Cancel')}
              </Button>
              <ProfessionalButton type="submit" disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                <Save className="mr-2 h-4 w-4" />
                {saving
                  ? t('common.saving', 'Saving...')
                  : t('common.save', 'Save')
                }
              </ProfessionalButton>
            </div>
          </form>
        </TabsContent>

        <TabsContent value="attachments" className="space-y-6">
          {isEdit && id ? (
            <div className="space-y-6">
              {/* Existing Attachments Gallery */}
              {attachments.length > 0 && (
                <AttachmentGallery
                  itemId={parseInt(id)}
                  attachments={attachments}
                  onAttachmentUpdate={() => loadAttachments(parseInt(id))}
                />
              )}

              {/* Upload New Attachments */}
              <AttachmentUpload
                itemId={parseInt(id)}
                onUploadComplete={handleAttachmentUpload}
                onUploadError={handleAttachmentUploadError}
              />
            </div>
          ) : (
            <ProfessionalCard>
              <CardContent className="p-8 text-center">
                <div className="text-muted-foreground">
                  <p className="text-lg font-medium mb-2">Save the item first</p>
                  <p>You can add attachments after creating the inventory item.</p>
                </div>
              </CardContent>
            </ProfessionalCard>
          )}
        </TabsContent>

        {isEdit && id && (
          <TabsContent value="activity" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Stock Movement Summary */}
              <ProfessionalCard>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Package className="h-5 w-5" />
                    {t('inventory.stock_movement_summary', 'Stock Movement Summary')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-8">
                    <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">
                      {t('inventory.stock_movement_placeholder', 'Stock movement summary will be displayed here')}
                    </p>
                  </div>
                </CardContent>
              </ProfessionalCard>

              {/* Linked Invoices */}
              <ProfessionalCard>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    {t('inventory.linked_invoices', 'Linked Invoices')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-8">
                    <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">
                      {t('inventory.linked_invoices_placeholder', 'Linked invoices will be displayed here')}
                    </p>
                  </div>
                </CardContent>
              </ProfessionalCard>
            </div>
          </TabsContent>
        )}
      </Tabs>

    </div>
  );
};

export default InventoryItemForm;
