import React, { useState, useEffect } from 'react';
import {
  Image as ImageIcon,
  FileText,
  Download,
  Trash2,
  Star,
  StarOff,
  MoreVertical,
  Eye,
  Edit,
  Grid,
  List,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { apiRequest } from '@/lib/api';

export interface Attachment {
  id: number;
  item_id: number;
  filename: string;
  stored_filename: string;
  file_path: string;
  file_size: number;
  content_type: string;
  file_hash: string;
  attachment_type: 'image' | 'document';
  document_type?: string;
  description?: string;
  alt_text?: string;
  is_primary: boolean;
  display_order: number;
  image_width?: number;
  image_height?: number;
  has_thumbnail: boolean;
  thumbnail_path?: string;
  uploaded_by: number;
  uploader_name?: string;
  created_at: string;
  updated_at: string;
}

interface AttachmentGalleryProps {
  itemId: number;
  attachments: Attachment[];
  onAttachmentUpdate?: () => void;
  viewMode?: 'grid' | 'list';
  className?: string;
}

export const AttachmentGallery: React.FC<AttachmentGalleryProps> = ({
  itemId,
  attachments,
  onAttachmentUpdate,
  viewMode: initialViewMode = 'grid',
  className
}) => {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(initialViewMode);
  const [selectedAttachment, setSelectedAttachment] = useState<Attachment | null>(null);
  const [editingAttachment, setEditingAttachment] = useState<Attachment | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewContentType, setPreviewContentType] = useState<string | null>(null);
  const [isContentTruncated, setIsContentTruncated] = useState(false);

  const imageAttachments = attachments.filter(att => att.attachment_type === 'image');
  const documentAttachments = attachments.filter(att => att.attachment_type === 'document');

  // Fetch blob URLs for image attachments
  React.useEffect(() => {
    const loadImageUrls = async () => {
      const newImageUrls: Record<number, string> = {};

      for (const attachment of imageAttachments) {
        const blobUrl = await fetchImageWithAuth(attachment.id);
        if (blobUrl) {
          newImageUrls[attachment.id] = blobUrl;
        }
      }

      setImageUrls(newImageUrls);
    };

    if (imageAttachments.length > 0) {
      loadImageUrls();
    }
  }, [attachments]);

  // Cleanup blob URLs on unmount
  React.useEffect(() => {
    return () => {
      Object.values(imageUrls).forEach(url => {
        URL.revokeObjectURL(url);
      });
    };
  }, [imageUrls]);

  const getFileIcon = (attachment: Attachment) => {
    if (attachment.attachment_type === 'image') {
      return <ImageIcon className="w-6 h-6 text-blue-500" />;
    } else if (attachment.content_type === 'application/pdf') {
      return <FileText className="w-6 h-6 text-red-500" />;
    } else {
      return <FileText className="w-6 h-6 text-gray-500" />;
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const fetchImageWithAuth = async (attachmentId: number): Promise<string | null> => {
    try {
      const response = await fetch(`/api/v1/inventory/${itemId}/attachments/${attachmentId}/download`, {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Failed to fetch image');
      }

      const contentType = response.headers.get('content-type');

      // Check if response is JSON (cloud URL response)
      if (contentType?.includes('application/json')) {
        const data = await response.json();
        if (data.type === 'cloud_url' && data.url) {
          // For cloud URLs, return the URL directly (it's pre-signed and doesn't need auth)
          return data.url;
        }
      }

      // Otherwise, it's a blob (local file served directly)
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    } catch (error) {
      console.error('Failed to fetch image with auth:', error);
      return null;
    }
  };

  const fetchAttachmentContent = async (attachmentId: number): Promise<{ content: string; contentType: string; isTruncated?: boolean } | null> => {
    try {
      const response = await fetch(`/api/v1/inventory/${itemId}/attachments/${attachmentId}/download`, {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Failed to fetch attachment');
      }

      const contentType = response.headers.get('content-type');

      // Check if response is JSON (cloud URL response)
      if (contentType?.includes('application/json')) {
        const data = await response.json();
        if (data.type === 'cloud_url' && data.url) {
          // For cloud URLs, fetch the content from the URL
          const urlResponse = await fetch(data.url);
          if (!urlResponse.ok) {
            throw new Error('Failed to fetch from cloud URL');
          }
          const blob = await urlResponse.blob();
          const blobContentType = urlResponse.headers.get('content-type') || blob.type || 'application/octet-stream';

          // For text files, read as text
          if (blobContentType.startsWith('text/') || blobContentType === 'application/json' || blobContentType === 'application/javascript') {
            const text = await blob.text();
            const lines = text.split('\n');
            const isTruncated = lines.length > 100;
            const truncatedContent = isTruncated ? lines.slice(0, 100).join('\n') + '\n\n[Content truncated - showing first 100 lines only]' : text;

            return {
              content: truncatedContent,
              contentType: blobContentType,
              isTruncated
            };
          }
          return null;
        }
      }

      // Otherwise, it's a blob (local file served directly)
      const blob = await response.blob();
      const blobContentType = contentType || blob.type || 'application/octet-stream';

      // For text files, read as text
      if (blobContentType.startsWith('text/') || blobContentType === 'application/json' || blobContentType === 'application/javascript') {
        const text = await blob.text();
        const lines = text.split('\n');
        const isTruncated = lines.length > 100;
        const truncatedContent = isTruncated ? lines.slice(0, 100).join('\n') + '\n\n[Content truncated - showing first 100 lines only]' : text;

        return {
          content: truncatedContent,
          contentType: blobContentType,
          isTruncated
        };
      }

      return null; // Not a text file
    } catch (error) {
      console.error('Failed to fetch attachment content:', error);
      return null;
    }
  };

  const handleDownload = async (attachment: Attachment) => {
    try {
      const response = await fetch(`/api/v1/inventory/${itemId}/attachments/${attachment.id}/download`, {
        credentials: 'include'
      });
      if (!response.ok) {
        throw new Error('Download failed');
      }

      const contentType = response.headers.get('content-type');

      // Check if response is JSON (cloud URL response)
      if (contentType?.includes('application/json')) {
        const data = await response.json();
        if (data.type === 'cloud_url' && data.url) {
          // For cloud URLs, fetch from the URL and download
          const urlResponse = await fetch(data.url);
          if (!urlResponse.ok) {
            throw new Error('Failed to fetch from cloud URL');
          }
          const blob = await urlResponse.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = data.filename || attachment.filename;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
          toast.success('File downloaded successfully');
          return;
        }
      }

      // Otherwise, it's a blob (local file served directly)
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = attachment.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success('File downloaded successfully');
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const handleDelete = async (attachment: Attachment) => {
    if (!confirm(`Are you sure you want to delete "${attachment.filename}"?`)) {
      return;
    }

    try {
      setLoading(true);
      await apiRequest(`/inventory/${itemId}/attachments/${attachment.id}`, {
        method: 'DELETE'
      });

      toast.success('Attachment deleted successfully');
      onAttachmentUpdate?.();
    } catch (error) {
      toast.error('Failed to delete attachment');
    } finally {
      setLoading(false);
    }
  };

  const handleSetPrimary = async (attachment: Attachment) => {
    try {
      setLoading(true);
      await apiRequest(`/inventory/${itemId}/attachments/${attachment.id}/set-primary`, {
        method: 'POST'
      });

      toast.success('Primary image updated');
      onAttachmentUpdate?.();
    } catch (error) {
      toast.error('Failed to set primary image');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateMetadata = async (attachmentId: number, metadata: Partial<Attachment>) => {
    try {
      setLoading(true);
      await apiRequest(`/inventory/${itemId}/attachments/${attachmentId}`, {
        method: 'PUT',
        body: JSON.stringify(metadata)
      });

      toast.success('Attachment updated successfully');
      setEditingAttachment(null);
      onAttachmentUpdate?.();
    } catch (error) {
      toast.error('Failed to update attachment');
    } finally {
      setLoading(false);
    }
  };

  const AttachmentCard: React.FC<{ attachment: Attachment }> = ({ attachment }) => {
    const [imageError, setImageError] = useState(false);

    const getThumbnailUrl = (attachment: Attachment) => {
      if (attachment.attachment_type === 'image') {
        // Use blob URL if available, otherwise fall back to direct download (which may not work without auth)
        return imageUrls[attachment.id] || `/api/v1/inventory/${itemId}/attachments/${attachment.id}/download`;
      }
      return null;
    };

    return (
      <Card className="group hover:shadow-md transition-shadow">
        <CardContent className="p-4">
          {/* Image Preview or Icon */}
          <div className="aspect-square bg-gray-100 rounded-lg mb-3 flex items-center justify-center overflow-hidden">
            {attachment.attachment_type === 'image' && !imageError ? (
              <img
                src={getThumbnailUrl(attachment)}
                alt={attachment.alt_text || attachment.filename}
                className="w-full h-full object-cover"
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="text-center">
                {getFileIcon(attachment)}
                <p className="text-xs text-gray-500 mt-1">
                  {attachment.content_type.split('/')[1]?.toUpperCase() || 'FILE'}
                </p>
              </div>
            )}
          </div>

          {/* File Info */}
          <div className="space-y-2">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-gray-900 truncate" title={attachment.filename}>
                  {attachment.filename}
                </h3>
                <p className="text-xs text-gray-500">
                  {formatFileSize(attachment.file_size)}
                </p>
              </div>

              {/* Primary Badge */}
              {attachment.is_primary && (
                <Badge variant="secondary" className="ml-2">
                  <Star className="w-3 h-3 mr-1" />
                  Primary
                </Badge>
              )}
            </div>

            {/* Description */}
            {attachment.description && (
              <p className="text-xs text-gray-600 line-clamp-2" title={attachment.description}>
                {attachment.description}
              </p>
            )}

            {/* Document Type */}
            {attachment.document_type && (
              <Badge variant="outline" className="text-xs">
                {attachment.document_type}
              </Badge>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex space-x-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={async () => {
                    setSelectedAttachment(attachment);
                    setPreviewContent(null);
                    setPreviewContentType(null);
                    setIsContentTruncated(false);

                    // For text files, fetch content for preview
                    if (attachment.content_type?.startsWith('text/') ||
                      attachment.content_type === 'application/json' ||
                      attachment.content_type === 'application/javascript') {
                      const contentResult = await fetchAttachmentContent(attachment.id);
                      if (contentResult) {
                        setPreviewContent(contentResult.content);
                        setPreviewContentType(contentResult.contentType);
                        setIsContentTruncated(contentResult.isTruncated || false);
                      }
                    }

                    setPreviewOpen(true);
                  }}
                  className="h-8 w-8 p-0"
                >
                  <Eye className="w-4 h-4" />
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDownload(attachment)}
                  className="h-8 w-8 p-0"
                >
                  <Download className="w-4 h-4" />
                </Button>
              </div>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setEditingAttachment(attachment)}>
                    <Edit className="w-4 h-4 mr-2" />
                    Edit
                  </DropdownMenuItem>

                  {attachment.attachment_type === 'image' && !attachment.is_primary && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => handleSetPrimary(attachment)}>
                        <Star className="w-4 h-4 mr-2" />
                        Set as Primary
                      </DropdownMenuItem>
                    </>
                  )}

                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => handleDelete(attachment)}
                    className="text-red-600"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const AttachmentListItem: React.FC<{ attachment: Attachment }> = ({ attachment }) => {
    return (
      <div className="flex items-center space-x-4 p-4 border rounded-lg hover:bg-gray-50">
        {/* Icon */}
        <div className="flex-shrink-0">
          {getFileIcon(attachment)}
        </div>

        {/* File Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-medium text-gray-900 truncate">
              {attachment.filename}
            </h3>
            {attachment.is_primary && (
              <Badge variant="secondary">
                <Star className="w-3 h-3 mr-1" />
                Primary
              </Badge>
            )}
          </div>

          <div className="flex items-center space-x-4 text-xs text-gray-500 mt-1">
            <span>{formatFileSize(attachment.file_size)}</span>
            <span>{attachment.attachment_type}</span>
            {attachment.document_type && <span>{attachment.document_type}</span>}
            <span>{new Date(attachment.created_at).toLocaleDateString()}</span>
          </div>

          {attachment.description && (
            <p className="text-sm text-gray-600 mt-1 truncate">
              {attachment.description}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              setSelectedAttachment(attachment);
              setPreviewContent(null);
              setPreviewContentType(null);
              setIsContentTruncated(false);

              // For text files, fetch content for preview
              if (attachment.content_type?.startsWith('text/') ||
                attachment.content_type === 'application/json' ||
                attachment.content_type === 'application/javascript') {
                const contentResult = await fetchAttachmentContent(attachment.id);
                if (contentResult) {
                  setPreviewContent(contentResult.content);
                  setPreviewContentType(contentResult.contentType);
                  setIsContentTruncated(contentResult.isTruncated || false);
                }
              }

              setPreviewOpen(true);
            }}
          >
            <Eye className="w-4 h-4 mr-2" />
            Preview
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDownload(attachment)}
          >
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreVertical className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setEditingAttachment(attachment)}>
                <Edit className="w-4 h-4 mr-2" />
                Edit
              </DropdownMenuItem>

              {attachment.attachment_type === 'image' && !attachment.is_primary && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => handleSetPrimary(attachment)}>
                    <Star className="w-4 h-4 mr-2" />
                    Set as Primary
                  </DropdownMenuItem>
                </>
              )}

              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => handleDelete(attachment)}
                className="text-red-600"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    );
  };

  if (attachments.length === 0) {
    return (
      <Card className={className}>
        <CardContent className="p-8 text-center">
          <ImageIcon className="mx-auto w-12 h-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No attachments yet</h3>
          <p className="text-gray-500">
            Upload images and documents to organize your inventory items.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Attachments</h2>
          <p className="text-sm text-gray-500">
            {imageAttachments.length} images, {documentAttachments.length} documents
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            variant={viewMode === 'grid' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('grid')}
          >
            <Grid className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('list')}
          >
            <List className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      )}

      {/* Attachments Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {attachments.map((attachment) => (
            <AttachmentCard key={attachment.id} attachment={attachment} />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {attachments.map((attachment) => (
            <AttachmentListItem key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}

      {/* Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={(open) => {
        setPreviewOpen(open);
        if (!open) {
          setPreviewContent(null);
          setPreviewContentType(null);
          setIsContentTruncated(false);
        }
      }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{selectedAttachment?.filename}</DialogTitle>
          </DialogHeader>

          {selectedAttachment && (
            <div className="space-y-4">
              {/* Image Preview */}
              {selectedAttachment.attachment_type === 'image' ? (
                <div className="flex justify-center">
                  <img
                    src={imageUrls[selectedAttachment.id] || `/api/v1/inventory/${itemId}/attachments/${selectedAttachment.id}/download`}
                    alt={selectedAttachment.alt_text || selectedAttachment.filename}
                    className="max-w-full max-h-96 object-contain rounded-lg"
                  />
                </div>
              ) : previewContent ? (
                <div className="bg-gray-50 rounded-lg p-4">
                  <pre className="text-sm whitespace-pre-wrap overflow-auto max-h-96 font-mono">
                    {previewContent}
                  </pre>
                </div>
              ) : (
                <div className="flex items-center justify-center p-8 bg-gray-50 rounded-lg">
                  {getFileIcon(selectedAttachment)}
                  <div className="ml-4">
                    <p className="font-medium">{selectedAttachment.filename}</p>
                    <p className="text-sm text-gray-500">
                      {formatFileSize(selectedAttachment.file_size)} • {selectedAttachment.content_type}
                    </p>
                  </div>
                </div>
              )}

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <Label className="font-medium">Type</Label>
                  <p className="capitalize">{selectedAttachment.attachment_type}</p>
                  {previewContent && previewContentType && (
                    <p className="text-xs text-gray-500 mt-1">{previewContentType}</p>
                  )}
                </div>

                <div>
                  <Label className="font-medium">Size</Label>
                  <p>{formatFileSize(selectedAttachment.file_size)}</p>
                  {isContentTruncated && (
                    <p className="text-xs text-orange-600 mt-1">Showing first 100 lines only</p>
                  )}
                </div>

                {selectedAttachment.document_type && (
                  <div>
                    <Label className="font-medium">Document Type</Label>
                    <p>{selectedAttachment.document_type}</p>
                  </div>
                )}

                <div>
                  <Label className="font-medium">Uploaded</Label>
                  <p>{new Date(selectedAttachment.created_at).toLocaleString()}</p>
                </div>

                {selectedAttachment.description && (
                  <div className="col-span-2">
                    <Label className="font-medium">Description</Label>
                    <p>{selectedAttachment.description}</p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => handleDownload(selectedAttachment)}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>

                {selectedAttachment.attachment_type === 'image' && !selectedAttachment.is_primary && (
                  <Button
                    variant="outline"
                    onClick={() => handleSetPrimary(selectedAttachment)}
                  >
                    <Star className="w-4 h-4 mr-2" />
                    Set as Primary
                  </Button>
                )}

                <Button
                  variant="outline"
                  onClick={() => setEditingAttachment(selectedAttachment)}
                >
                  <Edit className="w-4 h-4 mr-2" />
                  Edit
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={!!editingAttachment} onOpenChange={() => setEditingAttachment(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Attachment</DialogTitle>
          </DialogHeader>

          {editingAttachment && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const formData = new FormData(e.target as HTMLFormElement);
                const metadata = {
                  description: formData.get('description') as string,
                  alt_text: formData.get('alt_text') as string,
                  display_order: parseInt(formData.get('display_order') as string) || 0
                };
                handleUpdateMetadata(editingAttachment.id, metadata);
              }}
              className="space-y-4"
            >
              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  name="description"
                  defaultValue={editingAttachment.description || ''}
                  placeholder="Enter a description for this attachment"
                />
              </div>

              {editingAttachment.attachment_type === 'image' && (
                <div>
                  <Label htmlFor="alt_text">Alt Text</Label>
                  <Input
                    id="alt_text"
                    name="alt_text"
                    defaultValue={editingAttachment.alt_text || ''}
                    placeholder="Describe the image for accessibility"
                  />
                </div>
              )}

              <div>
                <Label htmlFor="display_order">Display Order</Label>
                <Input
                  id="display_order"
                  name="display_order"
                  type="number"
                  defaultValue={editingAttachment.display_order}
                  min="0"
                />
              </div>

              <div className="flex justify-end space-x-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditingAttachment(null)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Changes'
                  )}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AttachmentGallery;
