import React, { useState, useRef, useCallback } from 'react';
import { Button } from './button';
import { Input } from './input';
import { Upload, X, Eye, Trash2, CheckSquare, Square, FileText, Image as ImageIcon } from 'lucide-react';
import { toast } from 'sonner';

export interface FileData {
  file: File;
  name: string;
  size: number;
  type: string;
  originalSize?: number;
  compressed?: boolean;
  compressionRatio?: number;
  thumbnailUrl?: string;
  previewUrl?: string;
}

interface FileUploadProps {
  onFilesSelected: (files: FileData[]) => void;
  maxFiles?: number;
  allowedTypes?: string[];
  title?: string;
  maxFileSize?: number; // in MB
  selectedFiles?: FileData[];
  onRemoveFile?: (index: number) => void;
  uploading?: boolean;
  enableCompression?: boolean;
  enableBulkOperations?: boolean;
  customText?: {
    dragAndDrop?: string;
    supports?: string;
  };
}

export function FileUpload({
  onFilesSelected,
  maxFiles = 5,
  allowedTypes = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf'],
  title = 'Upload Files',
  maxFileSize = 10,
  selectedFiles = [],
  onRemoveFile,
  uploading = false,
  enableCompression = true,
  enableBulkOperations = true,
  customText,
}: FileUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [bulkMode, setBulkMode] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  const [previewFile, setPreviewFile] = useState<FileData | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // File Preview Functions
  const handleFilePreview = (fileData: FileData) => {
    setPreviewFile(fileData);
    setShowPreview(true);
  };

  // Compression Function
  const compressImage = useCallback(async (file: File): Promise<{ blob: Blob; compressed: boolean; compressionRatio?: number }> => {
    return new Promise((resolve) => {
      // Skip compression for small files
      if (file.size < 500 * 1024) { // Less than 500KB
        resolve({ blob: file, compressed: false });
        return;
      }

      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();

      img.onload = () => {
        // Calculate new dimensions (max 1200px width)
        const maxWidth = 1200;
        const ratio = Math.min(maxWidth / img.width, maxWidth / img.height);
        const newWidth = Math.floor(img.width * ratio);
        const newHeight = Math.floor(img.height * ratio);

        canvas.width = newWidth;
        canvas.height = newHeight;

        // Draw and compress
        ctx?.drawImage(img, 0, 0, newWidth, newHeight);

        canvas.toBlob(
          (blob) => {
            if (blob) {
              const compressionRatio = file.size / blob.size;
              resolve({
                blob,
                compressed: true,
                compressionRatio,
              });
            } else {
              resolve({ blob: file, compressed: false });
            }
          },
          'image/jpeg',
          0.8 // 80% quality
        );
      };

      img.onerror = () => {
        resolve({ blob: file, compressed: false });
      };

      img.src = URL.createObjectURL(file);
    });
  }, []);

  // Process Files
  const processFiles = useCallback(async (files: FileList | File[]): Promise<FileData[]> => {
    const fileArray = Array.from(files);
    const processedFiles: FileData[] = [];

    for (const file of fileArray) {
      // Validate file type
      if (!allowedTypes.includes(file.type)) {
        toast.error(`File type ${file.type} not allowed`);
        continue;
      }

      // Validate file size
      if (file.size > maxFileSize * 1024 * 1024) {
        toast.error(`File ${file.name} exceeds ${maxFileSize}MB limit`);
        continue;
      }

      let processedFile = file;
      let originalSize = file.size;
      let compressed = false;
      let compressionRatio;

      // Compress images if enabled
      if (enableCompression && file.type.startsWith('image/')) {
        try {
          const compressionResult = await compressImage(file);
          if (compressionResult.compressed) {
            processedFile = new File([compressionResult.blob], file.name, {
              type: compressionResult.blob.type,
              lastModified: Date.now(),
            });
            compressed = true;
            compressionRatio = compressionResult.compressionRatio;
          }
        } catch (error) {
          console.error('Compression failed:', error);
        }
      }

      // Create thumbnail for images
      let thumbnailUrl: string | undefined;
      let previewUrl: string | undefined;

      if (file.type.startsWith('image/')) {
        thumbnailUrl = URL.createObjectURL(processedFile);
        previewUrl = thumbnailUrl;
      }

      processedFiles.push({
        file: processedFile,
        name: file.name,
        size: processedFile.size,
        type: file.type,
        originalSize: compressed ? originalSize : undefined,
        compressed,
        compressionRatio,
        thumbnailUrl,
        previewUrl,
      });
    }

    return processedFiles;
  }, [allowedTypes, maxFileSize, enableCompression, compressImage]);

  // Handle File Selection
  const handleFileSelection = useCallback(async (files: FileList | File[]) => {
    const processedFiles = await processFiles(files);
    if (processedFiles.length > 0) {
      onFilesSelected(processedFiles);
    }
  }, [processFiles, onFilesSelected]);

  // Bulk Operations
  const toggleBulkMode = () => {
    setBulkMode(!bulkMode);
    setSelectedIndices(new Set());
  };

  const toggleFileSelection = (index: number) => {
    const newSelection = new Set(selectedIndices);
    if (newSelection.has(index)) {
      newSelection.delete(index);
    } else {
      newSelection.add(index);
    }
    setSelectedIndices(newSelection);
  };

  const bulkDelete = () => {
    if (selectedIndices.size === 0) return;

    const indicesToRemove = Array.from(selectedIndices).sort((a, b) => b - a);
    indicesToRemove.forEach(index => {
      if (onRemoveFile) onRemoveFile(index);
    });
    setSelectedIndices(new Set());
    setBulkMode(false);
    toast.success(`Deleted ${indicesToRemove.length} file(s)`);
  };

  // Drag and Drop
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files);
    }
  }, [handleFileSelection]);

  // File Type Icon
  const getFileTypeIcon = (type: string) => {
    if (type.startsWith('image/')) {
      return <ImageIcon className="w-5 h-5 text-blue-500" />;
    }
    return <FileText className="w-5 h-5 text-gray-500" />;
  };

  // Format File Size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">{title}</h3>
        {enableBulkOperations && selectedFiles.length > 0 && (
          <Button
            variant={bulkMode ? "default" : "outline"}
            size="sm"
            onClick={toggleBulkMode}
          >
            {bulkMode ? <X className="w-4 h-4 mr-2" /> : <CheckSquare className="w-4 h-4 mr-2" />}
            {bulkMode ? 'Cancel' : 'Select'}
          </Button>
        )}
      </div>

      {/* Selected Files */}
      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          {selectedFiles.map((fileData, index) => (
            <div
              key={index}
              className={`flex items-center justify-between p-3 border rounded-lg ${
                bulkMode && selectedIndices.has(index) ? 'bg-blue-50 border-blue-300' : 'bg-gray-50'
              }`}
            >
              {bulkMode && (
                <button
                  onClick={() => toggleFileSelection(index)}
                  className="mr-3"
                >
                  {selectedIndices.has(index) ? (
                    <CheckSquare className="w-5 h-5 text-blue-600" />
                  ) : (
                    <Square className="w-5 h-5 text-gray-400" />
                  )}
                </button>
              )}

              <div className="flex items-center flex-1 min-w-0">
                {getFileTypeIcon(fileData.type)}
                <div className="ml-3 flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{fileData.name}</p>
                  <p className="text-xs text-gray-500">
                    {formatFileSize(fileData.size)}
                    {fileData.originalSize && fileData.originalSize !== fileData.size && (
                      <span className="text-green-600 font-medium ml-1">
                        • Compressed {Math.round((1 - fileData.size / fileData.originalSize) * 100)}%
                      </span>
                    )}
                  </p>
                </div>
              </div>

              {fileData.previewUrl && !bulkMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleFilePreview(fileData)}
                  className="mr-2"
                >
                  <Eye className="w-4 h-4" />
                </Button>
              )}

              {onRemoveFile && !bulkMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemoveFile?.(index)}
                  disabled={uploading}
                >
                  <X className="w-4 h-4" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Bulk Actions */}
      {bulkMode && selectedIndices.size > 0 && (
        <div className="flex gap-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={bulkDelete}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete ({selectedIndices.size})
          </Button>
        </div>
      )}

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragActive
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
        <p className="text-sm text-gray-600 mb-2">
          {customText?.dragAndDrop || 'Drag and drop files here, or'}{' '}
          <button
            type="button"
            className="text-blue-600 hover:text-blue-800 font-medium"
            onClick={() => fileInputRef.current?.click()}
          >
            browse
          </button>
        </p>
        <p className="text-xs text-gray-500">
          {customText?.supports || `Supports: ${allowedTypes.join(', ')} • Max: ${maxFileSize}MB each`}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple={maxFiles > 1}
          accept={allowedTypes.join(',')}
          onChange={(e) => {
            if (e.target.files) {
              handleFileSelection(e.target.files);
            }
          }}
          className="hidden"
        />
      </div>

      {/* File Preview Modal */}
      {showPreview && previewFile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-medium truncate">{previewFile.name}</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowPreview(false)}
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
            <div className="p-4 flex justify-center">
              {previewFile.previewUrl ? (
                <img
                  src={previewFile.previewUrl}
                  alt={previewFile.name}
                  className="max-w-full max-h-96 object-contain"
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                  <FileText className="w-16 h-16 mb-4" />
                  <p>Preview not available</p>
                </div>
              )}
            </div>
            <div className="px-4 pb-4">
              <div className="text-sm text-gray-600 space-y-1">
                <p><strong>Type:</strong> {previewFile.type}</p>
                <p><strong>Size:</strong> {formatFileSize(previewFile.size)}</p>
                {previewFile.originalSize && previewFile.originalSize !== previewFile.size && (
                  <p className="text-green-600">
                    <strong>Compressed:</strong> {Math.round((1 - previewFile.size / previewFile.originalSize) * 100)}% reduction
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
