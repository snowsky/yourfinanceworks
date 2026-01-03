import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Edit,
  Package,
  DollarSign,
  Hash,
  Tag,
  Calendar,
  User,
  Image as ImageIcon,
  FileText,
  Download,
  Eye,
  Star,
  StarOff,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { inventoryApi, InventoryItem, getErrorMessage } from '@/lib/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { formatDateTime } from '@/lib/utils';
import { AttachmentGallery, Attachment } from '@/components/inventory/AttachmentGallery';
import { canPerformActions } from '@/utils/auth';
import { PageHeader } from '@/components/ui/professional-layout';

const InventoryItemDetail: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const [item, setItem] = useState<InventoryItem | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});

  const canPerformAction = canPerformActions();

  const fetchImageWithAuth = async (attachmentId: number): Promise<string | null> => {
    try {
      const response = await fetch(`/api/v1/inventory/${id}/attachments/${attachmentId}/download`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch image');
      }

      const blob = await response.blob();
      return URL.createObjectURL(blob);
    } catch (error) {
      console.error('Failed to fetch image with auth:', error);
      return null;
    }
  };

  useEffect(() => {
    if (id) {
      loadItem();
    }
  }, [id]);

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      Object.values(imageUrls).forEach(url => {
        URL.revokeObjectURL(url);
      });
    };
  }, [imageUrls]);

  const loadItem = async () => {
    try {
      setLoading(true);
      const itemData = await inventoryApi.getItem(parseInt(id!));
      setItem(itemData);
      await loadAttachments();
    } catch (err) {
      const errorMessage = getErrorMessage(err, t);
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const loadAttachments = async () => {
    try {
      setAttachmentsLoading(true);
      const response = await fetch(`/api/v1/inventory/${id}/attachments`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAttachments(data);

        // Fetch blob URLs for image attachments
        const imageAttachments = data.filter((att: Attachment) => att.attachment_type === 'image');
        const newImageUrls: Record<number, string> = {};

        for (const attachment of imageAttachments) {
          const blobUrl = await fetchImageWithAuth(attachment.id);
          if (blobUrl) {
            newImageUrls[attachment.id] = blobUrl;
          }
        }

        setImageUrls(newImageUrls);
      }
    } catch (error) {
      console.error('Failed to load attachments:', error);
    } finally {
      setAttachmentsLoading(false);
    }
  };

  const handleAttachmentUpdate = () => {
    loadAttachments();
  };

  if (loading) {
    return (
      <>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      </>
    );
  }

  if (error || !item) {
    return (
      <>
        <div className="h-full space-y-6 fade-in">
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => navigate('/inventory')}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t('common.back', 'Back')}
            </Button>
          </div>

          <Alert variant="destructive">
            <AlertDescription>
              {error || t('inventory.item_not_found', 'Item not found')}
            </AlertDescription>
          </Alert>
        </div>
      </>
    );
  }

  const imageAttachments = attachments.filter(att => att.attachment_type === 'image');
  const documentAttachments = attachments.filter(att => att.attachment_type === 'document');
  const primaryImage = attachments.find(att => att.is_primary && att.attachment_type === 'image');

  return (
    <div className="h-full space-y-6 fade-in">
      <PageHeader
        title={item.name}
        description={item.description || t('inventory.no_description', 'No description provided')}
        breadcrumbs={[
          { label: t('inventory.title', 'Inventory'), href: '/inventory' },
          { label: item.name }
        ]}
        actions={
          canPerformAction && (
            <Button asChild>
              <Link to={`/inventory/edit/${item.id}`}>
                <Edit className="mr-2 h-4 w-4" />
                {t('common.edit', 'Edit')}
              </Link>
            </Button>
          )
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Primary Image Display */}
          {primaryImage && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ImageIcon className="w-5 h-5" />
                  {t('inventory.primary_image', 'Primary Image')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden">
                  <img
                    src={imageUrls[primaryImage.id] || `/api/v1/inventory/${item.id}/attachments/${primaryImage.id}/download`}
                    alt={primaryImage.alt_text || primaryImage.filename}
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      e.currentTarget.src = '/placeholder-image.png';
                    }}
                  />
                </div>
                <div className="mt-3 flex items-center justify-between text-sm text-gray-600">
                  <span>{primaryImage.filename}</span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        try {
                          const response = await fetch(`/api/v1/inventory/${item.id}/attachments/${primaryImage.id}/download`, {
                            headers: {
                              'Authorization': `Bearer ${localStorage.getItem('token')}`
                            }
                          });

                          if (!response.ok) {
                            throw new Error('Download failed');
                          }

                          const blob = await response.blob();
                          const url = window.URL.createObjectURL(blob);
                          const link = document.createElement('a');
                          link.href = url;
                          link.download = primaryImage.filename;
                          document.body.appendChild(link);
                          link.click();
                          document.body.removeChild(link);
                          window.URL.revokeObjectURL(url);

                          toast.success('File downloaded successfully');
                        } catch (error) {
                          toast.error('Failed to download file');
                        }
                      }}
                    >
                      <Download className="w-4 h-4 mr-1" />
                      Download
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        try {
                          const response = await fetch(`/api/v1/inventory/${item.id}/attachments/${primaryImage.id}/download`, {
                            headers: {
                              'Authorization': `Bearer ${localStorage.getItem('token')}`
                            }
                          });

                          if (!response.ok) {
                            throw new Error('Failed to load image');
                          }

                          const blob = await response.blob();
                          const url = window.URL.createObjectURL(blob);
                          window.open(url, '_blank');
                        } catch (error) {
                          toast.error('Failed to open image');
                        }
                      }}
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      View Full Size
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Attachments Gallery */}
          {attachments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ImageIcon className="w-5 h-5" />
                    {t('inventory.attachments', 'Attachments')}
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="secondary">
                      {imageAttachments.length} {t('inventory.images', 'images')}
                    </Badge>
                    <Badge variant="outline">
                      {documentAttachments.length} {t('inventory.documents', 'documents')}
                    </Badge>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <AttachmentGallery
                  itemId={item.id}
                  attachments={attachments}
                  onAttachmentUpdate={handleAttachmentUpdate}
                  viewMode="grid"
                />
              </CardContent>
            </Card>
          )}

          {/* No Attachments Message */}
          {attachments.length === 0 && !attachmentsLoading && (
            <Card>
              <CardContent className="p-8 text-center">
                <ImageIcon className="mx-auto w-12 h-12 text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  {t('inventory.no_attachments', 'No attachments yet')}
                </h3>
                <p className="text-gray-500 mb-4">
                  {t('inventory.attachments_description', 'Add photos and documents to better organize your inventory items.')}
                </p>
                {canPerformAction && (
                  <Button asChild>
                    <Link to={`/inventory/edit/${item.id}`}>
                      <ImageIcon className="w-4 h-4 mr-2" />
                      {t('inventory.add_attachments', 'Add Attachments')}
                    </Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Item Details */}
          <Card>
            <CardHeader>
              <CardTitle>{t('inventory.item_details', 'Item Details')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('inventory.sku', 'SKU')}
                </span>
                <span className="text-sm font-mono">
                  {item.sku || t('common.none', 'None')}
                </span>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('inventory.unit_price', 'Unit Price')}
                </span>
                <CurrencyDisplay
                  amount={item.unit_price}
                  currency={item.currency}
                  className="text-sm font-medium"
                />
              </div>

              {item.cost_price && (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-500">
                      {t('inventory.cost_price', 'Cost Price')}
                    </span>
                    <CurrencyDisplay
                      amount={item.cost_price}
                      currency={item.currency}
                      className="text-sm"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-500">
                      {t('inventory.margin', 'Margin')}
                    </span>
                    <span className="text-sm">
                      {((item.unit_price - item.cost_price) / item.unit_price * 100).toFixed(1)}%
                    </span>
                  </div>
                </>
              )}

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('inventory.category', 'Category')}
                </span>
                <Badge variant="outline">
                  {item.category?.name || t('inventory.no_category', 'No Category')}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('inventory.item_type', 'Type')}
                </span>
                <Badge>
                  {item.item_type}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('inventory.unit_of_measure', 'Unit')}
                </span>
                <span className="text-sm">
                  {item.unit_of_measure}
                </span>
              </div>

              {item.track_stock && (
                <>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-500">
                      {t('inventory.current_stock', 'Current Stock')}
                    </span>
                    <span className="text-sm font-medium">
                      {item.current_stock}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-500">
                      {t('inventory.minimum_stock', 'Minimum Stock')}
                    </span>
                    <span className="text-sm">
                      {item.minimum_stock}
                    </span>
                  </div>
                </>
              )}

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('inventory.status', 'Status')}
                </span>
                <Badge variant={item.is_active ? "default" : "secondary"}>
                  {item.is_active ? t('common.active', 'Active') : t('common.inactive', 'Inactive')}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('common.created', 'Created')}
                </span>
                <span className="text-sm">
                  {formatDateTime(item.created_at)}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-500">
                  {t('common.updated', 'Updated')}
                </span>
                <span className="text-sm">
                  {formatDateTime(item.updated_at)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Quick Stats */}
          <Card>
            <CardHeader>
              <CardTitle>{t('inventory.quick_stats', 'Quick Stats')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">
                  {t('inventory.total_attachments', 'Total Attachments')}
                </span>
                <span className="text-sm font-medium">
                  {attachments.length}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">
                  {t('inventory.images', 'Images')}
                </span>
                <span className="text-sm font-medium">
                  {imageAttachments.length}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">
                  {t('inventory.documents', 'Documents')}
                </span>
                <span className="text-sm font-medium">
                  {documentAttachments.length}
                </span>
              </div>

              {attachments.length > 0 && (
                <>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">
                      {t('inventory.last_updated', 'Last Updated')}
                    </span>
                    <span className="text-sm font-medium">
                      {formatDateTime(new Date(Math.max(...attachments.map(a => new Date(a.updated_at).getTime()))))}
                    </span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default InventoryItemDetail;
