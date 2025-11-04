import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  Image,
  ScrollView,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import FileUpload, { FileData } from './FileUpload';
import LoadingIndicator from './LoadingIndicator';

const { width: screenWidth } = Dimensions.get('window');

interface EnhancedFileUploadProps {
  onFilesSelected: (files: FileData[]) => void;
  maxFiles?: number;
  allowedTypes?: string[];
  title?: string;
  selectedFiles?: FileData[];
  onRemoveFile?: (index: number) => void;
  uploading?: boolean;
  multiple?: boolean;
  showPreview?: boolean;
  maxFileSize?: number; // in MB
}

export const EnhancedFileUpload: React.FC<EnhancedFileUploadProps> = ({
  onFilesSelected,
  maxFiles = 10,
  allowedTypes = ['image/*', 'application/pdf'],
  title = 'Select Files',
  selectedFiles = [],
  onRemoveFile,
  uploading = false,
  multiple = true,
  showPreview = true,
  maxFileSize = 10,
}) => {
  const [showOptions, setShowOptions] = useState(false);

  const requestPermissions = async () => {
    const { status: cameraStatus } = await ImagePicker.requestCameraPermissionsAsync();
    const { status: libraryStatus } = await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (cameraStatus !== 'granted' || libraryStatus !== 'granted') {
      Alert.alert(
        'Permissions Required',
        'Camera and media library permissions are required to upload files.',
        [{ text: 'OK' }]
      );
      return false;
    }
    return true;
  };

  const pickFromGallery = async () => {
    try {
      const hasPermission = await requestPermissions();
      if (!hasPermission) return;

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images', 'videos'],
        allowsEditing: false,
        quality: 0.8,
        allowsMultipleSelection: multiple,
        selectionLimit: maxFiles - selectedFiles.length,
      });

      if (!result.canceled && result.assets) {
        const files: FileData[] = result.assets.map((asset, index) => ({
          uri: asset.uri,
          name: asset.fileName || `image_${Date.now()}_${index}.jpg`,
          type: asset.type === 'image' ? 'image/jpeg' : asset.mimeType || 'application/octet-stream',
          size: asset.fileSize,
          originalSize: asset.fileSize,
        }));

        // Filter by file size
        const validFiles = files.filter(file => {
          const fileSizeMB = (file.size || 0) / (1024 * 1024);
          if (fileSizeMB > maxFileSize) {
            Alert.alert('File Too Large', `${file.name} is ${fileSizeMB.toFixed(1)}MB. Maximum size is ${maxFileSize}MB.`);
            return false;
          }
          return true;
        });

        if (validFiles.length > 0) {
          onFilesSelected(validFiles);
        }
      }
    } catch (error) {
      console.error('Error picking from gallery:', error);
      Alert.alert('Error', 'Failed to pick files from gallery');
    }
    setShowOptions(false);
  };

  const takePhoto = async () => {
    try {
      const hasPermission = await requestPermissions();
      if (!hasPermission) return;

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        allowsEditing: false,
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets[0]) {
        const asset = result.assets[0];
        const compressedImage = await manipulateAsync(
          asset.uri,
          [{ resize: { width: 1200 } }],
          { compress: 0.8, format: SaveFormat.JPEG }
        );

        const file: FileData = {
          uri: compressedImage.uri,
          name: `photo_${Date.now()}.jpg`,
          type: 'image/jpeg',
          size: asset.fileSize,
          originalSize: asset.fileSize,
          compressed: true,
          compressionRatio: asset.fileSize ? compressedImage.width / asset.width : 1,
        };

        onFilesSelected([file]);
      }
    } catch (error) {
      console.error('Error taking photo:', error);
      Alert.alert('Error', 'Failed to take photo');
    }
    setShowOptions(false);
  };

  const pickDocument = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: allowedTypes.includes('application/pdf') ? 'application/pdf' : '*/*',
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const fileData: FileData[] = result.assets.map(asset => ({
          uri: asset.uri,
          name: asset.name,
          type: asset.mimeType || 'application/octet-stream',
          size: asset.size,
        }));

        onFilesSelected(fileData);
      }
    } catch (error) {
      console.error('Error picking document:', error);
      Alert.alert('Error', 'Failed to pick document');
    }
    setShowOptions(false);
  };

  const renderFilePreview = (file: FileData, index: number) => {
    const isImage = file.type?.startsWith('image/');
    const fileSizeMB = file.size ? (file.size / (1024 * 1024)).toFixed(1) : '0';

    return (
      <View key={index} style={styles.filePreview}>
        {isImage && file.uri ? (
          <Image source={{ uri: file.uri }} style={styles.fileImage} />
        ) : (
          <View style={styles.fileIcon}>
            <Ionicons name="document" size={24} color="#6B7280" />
          </View>
        )}

        <View style={styles.fileInfo}>
          <Text style={styles.fileName} numberOfLines={1}>
            {file.name}
          </Text>
          <Text style={styles.fileSize}>
            {fileSizeMB} MB
          </Text>
        </View>

        {onRemoveFile && (
          <TouchableOpacity
            style={styles.removeButton}
            onPress={() => onRemoveFile(index)}
            disabled={uploading}
          >
            <Ionicons name="close-circle" size={20} color="#EF4444" />
          </TouchableOpacity>
        )}

        {file.compressed && (
          <View style={styles.compressedBadge}>
            <Text style={styles.compressedText}>Compressed</Text>
          </View>
        )}
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {title && <Text style={styles.title}>{title}</Text>}

      {/* Upload Options */}
      <View style={styles.uploadOptions}>
        <TouchableOpacity
          style={styles.uploadButton}
          onPress={() => setShowOptions(!showOptions)}
          disabled={uploading}
        >
          <Ionicons name="add-circle" size={24} color="#007AFF" />
          <Text style={styles.uploadButtonText}>
            {selectedFiles.length > 0
              ? `Add More Files (${selectedFiles.length}/${maxFiles})`
              : 'Select Files'
            }
          </Text>
          <Ionicons
            name={showOptions ? "chevron-up" : "chevron-down"}
            size={16}
            color="#6B7280"
          />
        </TouchableOpacity>

        {showOptions && (
          <View style={styles.optionsContainer}>
            <TouchableOpacity style={styles.optionButton} onPress={pickFromGallery}>
              <Ionicons name="images" size={20} color="#007AFF" />
              <Text style={styles.optionText}>Photo Library</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.optionButton} onPress={takePhoto}>
              <Ionicons name="camera" size={20} color="#10B981" />
              <Text style={styles.optionText}>Take Photo</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.optionButton} onPress={pickDocument}>
              <Ionicons name="document" size={20} color="#F59E0B" />
              <Text style={styles.optionText}>Documents</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* File Previews */}
      {showPreview && selectedFiles.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.filesContainer}
        >
          {selectedFiles.map((file, index) => renderFilePreview(file, index))}
        </ScrollView>
      )}

      {/* Upload Progress */}
      {uploading && (
        <LoadingIndicator
          message="Uploading files..."
          size="small"
          style={styles.uploadProgress}
        />
      )}

      {/* File Count Info */}
      {selectedFiles.length > 0 && (
        <Text style={styles.fileCount}>
          {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected
        </Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 12,
  },
  uploadOptions: {
    marginBottom: 12,
  },
  uploadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: '#D1D5DB',
  },
  uploadButtonText: {
    flex: 1,
    fontSize: 16,
    color: '#374151',
    marginLeft: 8,
  },
  optionsContainer: {
    marginTop: 8,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    overflow: 'hidden',
  },
  optionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  optionText: {
    fontSize: 16,
    color: '#374151',
    marginLeft: 12,
  },
  filesContainer: {
    marginTop: 8,
  },
  filePreview: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 12,
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    minWidth: screenWidth * 0.7,
  },
  fileImage: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 12,
  },
  fileIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  fileInfo: {
    flex: 1,
  },
  fileName: {
    fontSize: 14,
    fontWeight: '500',
    color: '#111827',
    marginBottom: 2,
  },
  fileSize: {
    fontSize: 12,
    color: '#6B7280',
  },
  removeButton: {
    padding: 4,
    marginLeft: 8,
  },
  compressedBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: '#10B981',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
  },
  compressedText: {
    fontSize: 10,
    color: '#fff',
    fontWeight: '600',
  },
  uploadProgress: {
    marginTop: 12,
  },
  fileCount: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
    marginTop: 8,
  },
});

export default EnhancedFileUpload;
