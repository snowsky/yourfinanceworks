import React, { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload,
  X,
  File,
  Image as ImageIcon,
  AlertCircle,
  CheckCircle,
  Loader2,
  FileText,
  Camera
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export interface FileUploadItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  progress: number;
  error?: string;
  preview?: string;
}

interface AttachmentUploadProps {
  itemId: number;
  onUploadComplete?: (attachments: any[]) => void;
  onUploadError?: (error: string) => void;
  maxFiles?: number;
  maxFileSize?: number; // in MB
  allowedTypes?: string[];
  className?: string;
}

const ALLOWED_IMAGE_TYPES = [
  'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
  'image/webp', 'image/bmp', 'image/tiff'
];

const ALLOWED_DOCUMENT_TYPES = [
  'application/pdf', 'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain', 'text/csv'
];

export const AttachmentUpload: React.FC<AttachmentUploadProps> = ({
  itemId,
  onUploadComplete,
  onUploadError,
  maxFiles = 10,
  maxFileSize = 10, // 10MB default
  allowedTypes = [...ALLOWED_IMAGE_TYPES, ...ALLOWED_DOCUMENT_TYPES],
  className
}) => {
  const [uploadItems, setUploadItems] = useState<FileUploadItem[]>([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    // Check file size
    if (file.size > maxFileSize * 1024 * 1024) {
      return `File size exceeds ${maxFileSize}MB limit`;
    }

    // Check file type
    if (!allowedTypes.includes(file.type)) {
      return `File type ${file.type} is not allowed`;
    }

    return null;
  };

  const createPreview = (file: File): Promise<string | undefined> => {
    return new Promise((resolve) => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          resolve(e.target?.result as string);
        };
        reader.readAsDataURL(file);
      } else {
        resolve(undefined);
      }
    });
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(file => {
      const error = validateFile(file);
      if (error) {
        onUploadError?.(error);
        return false;
      }
      return true;
    });

    if (validFiles.length === 0) return;

    // Check total file limit
    const currentCount = uploadItems.length;
    const availableSlots = maxFiles - currentCount;
    const filesToAdd = validFiles.slice(0, availableSlots);

    if (filesToAdd.length < validFiles.length) {
      onUploadError?.(`Maximum ${maxFiles} files allowed. Only first ${availableSlots} files will be added.`);
    }

    // Create upload items with previews
    const newItems: FileUploadItem[] = await Promise.all(
      filesToAdd.map(async (file) => {
        const preview = await createPreview(file);
        return {
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file,
          status: 'pending' as const,
          progress: 0,
          preview
        };
      })
    );

    setUploadItems(prev => [...prev, ...newItems]);
  }, [uploadItems.length, maxFiles, maxFileSize, allowedTypes, onUploadError]);

  const { getRootProps, getInputProps, isDragActive: dropzoneDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ALLOWED_IMAGE_TYPES.map(type => type.replace('image/', '.')),
      // 'application/*': ALLOWED_DOCUMENT_TYPES
    },
    maxSize: maxFileSize * 1024 * 1024,
    multiple: true,
    disabled: uploadItems.length >= maxFiles || isUploading
  });

  const removeFile = (id: string) => {
    setUploadItems(prev => prev.filter(item => item.id !== id));
  };

  const uploadFile = async (uploadItem: FileUploadItem): Promise<any> => {
    const formData = new FormData();
    formData.append('file', uploadItem.file);

    // Determine attachment type
    const attachmentType = uploadItem.file.type.startsWith('image/') ? 'image' : 'document';
    formData.append('attachment_type', attachmentType);

    // Add description if it's an image
    if (attachmentType === 'image') {
      formData.append('description', `Uploaded image: ${uploadItem.file.name}`);
    } else {
      formData.append('description', `Uploaded document: ${uploadItem.file.name}`);
    }

    try {
      const response = await fetch(`/api/v1/inventory/${itemId}/attachments`, {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const result = await response.json();
      return result;
    } catch (error) {
      throw error;
    }
  };

  const uploadAllFiles = async () => {
    if (uploadItems.length === 0) return;

    setIsUploading(true);
    const results: any[] = [];
    const errors: string[] = [];

    // Upload files sequentially to avoid overwhelming the server
    for (let i = 0; i < uploadItems.length; i++) {
      const item = uploadItems[i];

      // Update status to uploading
      setUploadItems(prev => prev.map(uploadItem =>
        uploadItem.id === item.id
          ? { ...uploadItem, status: 'uploading', progress: 10 }
          : uploadItem
      ));

      try {
        // Simulate progress updates
        const progressInterval = setInterval(() => {
          setUploadItems(prev => prev.map(uploadItem =>
            uploadItem.id === item.id && uploadItem.progress < 90
              ? { ...uploadItem, progress: uploadItem.progress + 10 }
              : uploadItem
          ));
        }, 200);

        const result = await uploadFile(item);

        clearInterval(progressInterval);

        // Update status to completed
        setUploadItems(prev => prev.map(uploadItem =>
          uploadItem.id === item.id
            ? { ...uploadItem, status: 'completed', progress: 100 }
            : uploadItem
        ));

        results.push(result);

      } catch (error) {
        // Update status to error
        setUploadItems(prev => prev.map(uploadItem =>
          uploadItem.id === item.id
            ? {
                ...uploadItem,
                status: 'error',
                progress: 0,
                error: error instanceof Error ? error.message : 'Upload failed'
              }
            : uploadItem
        ));

        errors.push(`${item.file.name}: ${error instanceof Error ? error.message : 'Upload failed'}`);
      }
    }

    setIsUploading(false);

    if (results.length > 0) {
      onUploadComplete?.(results);
    }

    if (errors.length > 0) {
      onUploadError?.(`Upload errors:\n${errors.join('\n')}`);
    }

    // Clear completed and error items after a delay
    setTimeout(() => {
      setUploadItems(prev => prev.filter(item =>
        item.status !== 'completed' && item.status !== 'error'
      ));
    }, 3000);
  };

  const clearAllFiles = () => {
    setUploadItems([]);
  };

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) {
      return <ImageIcon className="w-8 h-8 text-blue-500" />;
    } else if (file.type === 'application/pdf') {
      return <FileText className="w-8 h-8 text-red-500" />;
    } else {
      return <File className="w-8 h-8 text-gray-500" />;
    }
  };

  const getStatusIcon = (status: FileUploadItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'uploading':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return null;
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Upload Zone */}
      <Card>
        <CardContent className="p-6">
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
              dropzoneDragActive || isDragActive
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400",
              (uploadItems.length >= maxFiles || isUploading) && "opacity-50 cursor-not-allowed"
            )}
          >
            <input {...getInputProps()} ref={fileInputRef} />
            <Upload className="mx-auto w-12 h-12 text-gray-400 mb-4" />
            <p className="text-lg font-medium text-gray-900 mb-2">
              {dropzoneDragActive ? 'Drop files here' : 'Drag & drop files here'}
            </p>
            <p className="text-sm text-gray-500 mb-4">
              or{' '}
              <button
                type="button"
                className="text-blue-600 hover:text-blue-500 font-medium"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadItems.length >= maxFiles || isUploading}
              >
                browse files
              </button>
            </p>
            <div className="text-xs text-gray-400 space-y-1">
              <p>Maximum {maxFiles} files, up to {maxFileSize}MB each</p>
              <p>Supported: Images (JPEG, PNG, WebP, GIF) and Documents (PDF, Word, Excel, TXT)</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* File List */}
      {uploadItems.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-900">
                  Files to upload ({uploadItems.length})
                </h3>
                <div className="flex space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearAllFiles}
                    disabled={isUploading}
                  >
                    Clear All
                  </Button>
                  <Button
                    size="sm"
                    onClick={uploadAllFiles}
                    disabled={isUploading}
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        Upload All
                      </>
                    )}
                  </Button>
                </div>
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {uploadItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg"
                  >
                    {/* File Preview/Icon */}
                    <div className="flex-shrink-0">
                      {item.preview ? (
                        <img
                          src={item.preview}
                          alt={item.file.name}
                          className="w-10 h-10 object-cover rounded"
                        />
                      ) : (
                        getFileIcon(item.file)
                      )}
                    </div>

                    {/* File Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {item.file.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {(item.file.size / 1024 / 1024).toFixed(2)} MB
                      </p>

                      {/* Progress Bar */}
                      {item.status === 'uploading' && (
                        <Progress value={item.progress} className="mt-2 h-1" />
                      )}

                      {/* Error Message */}
                      {item.status === 'error' && item.error && (
                        <p className="text-xs text-red-600 mt-1">{item.error}</p>
                      )}
                    </div>

                    {/* Status Icon */}
                    <div className="flex-shrink-0">
                      {getStatusIcon(item.status)}
                    </div>

                    {/* Remove Button */}
                    {item.status === 'pending' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFile(item.id)}
                        disabled={isUploading}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Usage Info */}
      <div className="text-xs text-gray-500 text-center">
        <p>Files are securely stored and organized by inventory item.</p>
        <p>Images are automatically optimized for web display.</p>
      </div>
    </div>
  );
};

export default AttachmentUpload;
