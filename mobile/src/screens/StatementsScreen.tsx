import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import * as DocumentPicker from 'expo-document-picker';
import apiService, { BankStatement } from '../services/api';
import StatusIndicator from '../components/StatusIndicator';

interface BankStatementsScreenProps {
  onNavigateBack: () => void;
  onNavigateToStatement: (statement: BankStatement) => void;
}

const BankStatementsScreen: React.FC<BankStatementsScreenProps> = ({
  onNavigateBack,
  onNavigateToStatement,
}) => {
  const { t } = useTranslation();
  const [statements, setStatements] = useState<BankStatement[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchStatements();
  }, []);

  const fetchStatements = async () => {
    try {
      setLoading(true);
      const data = await apiService.getBankStatements();
      setStatements(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to fetch bank statements:', error);
      Alert.alert('Error', 'Failed to load bank statements');
      setStatements([]); // Ensure statements is always an array
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchStatements();
    setRefreshing(false);
  };

  const handleUpload = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['application/pdf', 'text/csv'],
        multiple: true,
        copyToCacheDirectory: true,
      });

      if (!result.canceled && result.assets.length > 0) {
        setUploading(true);
        
        // Convert to File-like objects for API
        const files = result.assets.map(asset => ({
          uri: asset.uri,
          name: asset.name,
          type: asset.mimeType || 'application/pdf',
        }));

        await apiService.uploadBankStatements(files);
        Alert.alert('Success', 'Bank statements uploaded successfully');
        await fetchStatements();
      }
    } catch (error) {
      console.error('Failed to upload bank statements:', error);
      Alert.alert('Error', 'Failed to upload bank statements');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteStatement = async (id: number) => {
    Alert.alert(
      t('statements.delete_statement'),
      t('statements.delete_confirm_description'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.delete'),
          style: 'destructive',
          onPress: async () => {
            try {
              await apiService.deleteBankStatement(id);
              setStatements(prev => prev.filter(s => s.id !== id));
              Alert.alert(t('common.success'), t('statements.statement_deleted'));
            } catch (error) {
              console.error('Failed to delete bank statement:', error);
              Alert.alert(t('common.error'), t('statements.failed_to_delete'));
            }
          },
        },
      ]
    );
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processed': return '#10B981';
      case 'processing': return '#F59E0B';
      case 'failed': return '#EF4444';
      default: return '#6B7280';
    }
  };

  const formatStatus = (status: string) => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading bank statements...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Bank Statements</Text>
        <TouchableOpacity
          style={[styles.uploadButton, uploading && styles.uploadButtonDisabled]}
          onPress={handleUpload}
          disabled={uploading}
        >
          {uploading ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Ionicons name="cloud-upload" size={20} color="#FFFFFF" />
          )}
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        showsVerticalScrollIndicator={false}
      >
        {statements.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="document-text-outline" size={64} color="#9CA3AF" />
            <Text style={styles.emptyStateText}>No bank statements</Text>
            <Text style={styles.emptyStateSubtext}>
              Upload PDF or CSV files to get started with transaction analysis
            </Text>
            <TouchableOpacity style={styles.emptyStateButton} onPress={handleUpload}>
              <Ionicons name="cloud-upload" size={20} color="#FFFFFF" />
              <Text style={styles.emptyStateButtonText}>Upload Statements</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.statementsList}>
            {statements.map((statement) => {
              const creatorName = statement.created_by_username || statement.created_by_email || t('common.unknown');
              
              return (
                <View key={statement.id} style={styles.statementCard}>
                  <TouchableOpacity
                    style={styles.statementContent}
                    onPress={() => onNavigateToStatement(statement)}
                  >
                    <View style={styles.statementHeader}>
                      <View style={styles.statementInfo}>
                        <Text style={styles.statementFilename} numberOfLines={2}>
                          {statement.original_filename}
                        </Text>
                        <View style={styles.statementMeta}>
                          <StatusIndicator
                            status={statement.status as any}
                            size="small"
                            customText={formatStatus(statement.status)}
                          />
                          <Text style={styles.transactionCount}>
                            {statement.extracted_count} transactions
                          </Text>
                        </View>
                      </View>
                      <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
                    </View>
                    
                    <View style={styles.statementDetails}>
                      <Text style={styles.statementDate}>
                        Uploaded: {formatDate(statement.created_at)}
                      </Text>
                      <Text style={styles.statementCreator}>
                        Created by: {creatorName}
                      </Text>
                      {statement.labels && statement.labels.length > 0 && (
                        <View style={styles.labelsContainer}>
                          {statement.labels.slice(0, 3).map((label, index) => (
                            <View key={index} style={styles.labelBadge}>
                              <Text style={styles.labelText}>{label}</Text>
                            </View>
                          ))}
                          {statement.labels.length > 3 && (
                            <Text style={styles.moreLabels}>+{statement.labels.length - 3} more</Text>
                          )}
                        </View>
                      )}
                    </View>
                  </TouchableOpacity>

                  <View style={styles.statementActions}>
                    <TouchableOpacity
                      style={styles.actionButton}
                      onPress={() => onNavigateToStatement(statement)}
                    >
                      <Ionicons name="eye-outline" size={16} color="#3B82F6" />
                      <Text style={styles.actionButtonText}>{t('common.view')}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.actionButton, styles.deleteButton]}
                      onPress={() => handleDeleteStatement(statement.id)}
                    >
                      <Ionicons name="trash-outline" size={16} color="#EF4444" />
                      <Text style={[styles.actionButtonText, styles.deleteButtonText]}>{t('common.delete')}</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B7280',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 20,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
  },
  uploadButton: {
    backgroundColor: '#3B82F6',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  uploadButtonDisabled: {
    backgroundColor: '#9CA3AF',
  },
  scrollView: {
    flex: 1,
  },
  statementsList: {
    padding: 20,
  },
  statementCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  statementContent: {
    padding: 16,
  },
  statementHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  statementInfo: {
    flex: 1,
    marginRight: 12,
  },
  statementFilename: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 8,
  },
  statementMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    color: '#FFFFFF',
    fontWeight: '500',
  },
  transactionCount: {
    fontSize: 14,
    color: '#6B7280',
  },
  statementDetails: {
    gap: 8,
  },
  statementDate: {
    fontSize: 14,
    color: '#6B7280',
  },
  statementCreator: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 4,
    fontStyle: 'italic',
  },
  labelsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 6,
  },
  labelBadge: {
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
  },
  labelText: {
    fontSize: 12,
    color: '#374151',
    fontWeight: '500',
  },
  moreLabels: {
    fontSize: 12,
    color: '#6B7280',
    fontStyle: 'italic',
  },
  statementActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingBottom: 16,
    gap: 12,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#F3F4F6',
    gap: 4,
  },
  actionButtonText: {
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
  },
  deleteButton: {
    backgroundColor: '#FEF2F2',
  },
  deleteButtonText: {
    color: '#EF4444',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 80,
    paddingHorizontal: 40,
  },
  emptyStateText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
    marginBottom: 8,
    textAlign: 'center',
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  emptyStateButton: {
    backgroundColor: '#3B82F6',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
    gap: 8,
  },
  emptyStateButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default BankStatementsScreen;