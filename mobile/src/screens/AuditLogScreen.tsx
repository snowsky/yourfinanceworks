import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  TextInput,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import apiService from '../services/api';

interface AuditLogEntry {
  id: number;
  user_id: number;
  user_name: string;
  action: string;
  resource_type: string;
  resource_id: number;
  details: string;
  ip_address: string;
  user_agent: string;
  created_at: string;
}

interface AuditLogScreenProps {
  onNavigateBack: () => void;
}

const AuditLogScreen: React.FC<AuditLogScreenProps> = ({ onNavigateBack }) => {
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<AuditLogEntry | null>(null);

  useEffect(() => {
    fetchAuditLogs();
  }, []);

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      // Note: This endpoint might need to be implemented in the API
      const response = await apiService.request<AuditLogEntry[]>('/audit-log/');
      setAuditLogs(response);
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
      Alert.alert('Error', 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = auditLogs.filter(log =>
    log.user_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.resource_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.details.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getActionColor = (action: string) => {
    switch (action.toLowerCase()) {
      case 'create': return '#10B981';
      case 'update': return '#F59E0B';
      case 'delete': return '#EF4444';
      case 'login': return '#3B82F6';
      case 'logout': return '#6B7280';
      default: return '#6B7280';
    }
  };

  const getActionIcon = (action: string) => {
    switch (action.toLowerCase()) {
      case 'create': return 'add-circle-outline';
      case 'update': return 'create-outline';
      case 'delete': return 'trash-outline';
      case 'login': return 'log-in-outline';
      case 'logout': return 'log-out-outline';
      default: return 'information-circle-outline';
    }
  };

  const AuditLogItem = ({ entry }: { entry: AuditLogEntry }) => (
    <TouchableOpacity
      style={styles.logItem}
      onPress={() => setSelectedEntry(entry)}
    >
      <View style={styles.logHeader}>
        <View style={styles.actionContainer}>
          <View style={[styles.actionIcon, { backgroundColor: getActionColor(entry.action) + '20' }]}>
            <Ionicons
              name={getActionIcon(entry.action) as any}
              size={16}
              color={getActionColor(entry.action)}
            />
          </View>
          <View style={styles.actionInfo}>
            <Text style={styles.actionText}>{entry.action.toUpperCase()}</Text>
            <Text style={styles.resourceText}>{entry.resource_type}</Text>
          </View>
        </View>
        <Text style={styles.timeText}>
          {new Date(entry.created_at).toLocaleTimeString()}
        </Text>
      </View>
      
      <View style={styles.logContent}>
        <Text style={styles.userText}>by {entry.user_name}</Text>
        <Text style={styles.detailsText} numberOfLines={2}>
          {entry.details}
        </Text>
      </View>
      
      <Text style={styles.dateText}>
        {new Date(entry.created_at).toLocaleDateString()}
      </Text>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading audit logs...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#333" />
        </TouchableOpacity>
        <Text style={styles.title}>Audit Log</Text>
        <TouchableOpacity style={styles.refreshButton} onPress={fetchAuditLogs}>
          <Ionicons name="refresh" size={20} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#6B7280" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="Search audit logs..."
          placeholderTextColor="#9CA3AF"
        />
      </View>

      <ScrollView style={styles.content}>
        {filteredLogs.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="document-text-outline" size={64} color="#9CA3AF" />
            <Text style={styles.emptyTitle}>No audit logs found</Text>
            <Text style={styles.emptyDescription}>
              {searchQuery ? 'Try adjusting your search' : 'No activity recorded yet'}
            </Text>
          </View>
        ) : (
          <View style={styles.logsList}>
            {filteredLogs.map((entry) => (
              <AuditLogItem key={entry.id} entry={entry} />
            ))}
          </View>
        )}
      </ScrollView>

      {selectedEntry && (
        <View style={styles.modal}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Audit Log Details</Text>
              <TouchableOpacity onPress={() => setSelectedEntry(null)}>
                <Ionicons name="close" size={24} color="#333" />
              </TouchableOpacity>
            </View>
            
            <ScrollView style={styles.modalBody}>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Action:</Text>
                <View style={[styles.actionBadge, { backgroundColor: getActionColor(selectedEntry.action) + '20' }]}>
                  <Text style={[styles.actionBadgeText, { color: getActionColor(selectedEntry.action) }]}>
                    {selectedEntry.action.toUpperCase()}
                  </Text>
                </View>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>User:</Text>
                <Text style={styles.detailValue}>{selectedEntry.user_name}</Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Resource:</Text>
                <Text style={styles.detailValue}>{selectedEntry.resource_type} (ID: {selectedEntry.resource_id})</Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Time:</Text>
                <Text style={styles.detailValue}>
                  {new Date(selectedEntry.created_at).toLocaleString()}
                </Text>
              </View>

              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>IP Address:</Text>
                <Text style={styles.detailValue}>{selectedEntry.ip_address}</Text>
              </View>

              <View style={styles.detailColumn}>
                <Text style={styles.detailLabel}>Details:</Text>
                <Text style={styles.detailValueMultiline}>{selectedEntry.details}</Text>
              </View>

              <View style={styles.detailColumn}>
                <Text style={styles.detailLabel}>User Agent:</Text>
                <Text style={styles.detailValueMultiline}>{selectedEntry.user_agent}</Text>
              </View>
            </ScrollView>
          </View>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F8FAFC' },
  loadingText: { marginTop: 16, fontSize: 16, color: '#6B7280' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 60, paddingBottom: 20, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#E5E7EB' },
  backButton: { padding: 8 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#111827' },
  refreshButton: { padding: 8 },
  searchContainer: { flexDirection: 'row', alignItems: 'center', margin: 20, backgroundColor: '#fff', borderRadius: 12, paddingHorizontal: 16, borderWidth: 1, borderColor: '#E5E7EB' },
  searchIcon: { marginRight: 12 },
  searchInput: { flex: 1, paddingVertical: 12, fontSize: 16, color: '#111827' },
  content: { flex: 1 },
  emptyState: { alignItems: 'center', justifyContent: 'center', paddingVertical: 60 },
  emptyTitle: { fontSize: 18, fontWeight: 'bold', color: '#111827', marginTop: 16 },
  emptyDescription: { fontSize: 14, color: '#6B7280', textAlign: 'center', marginTop: 8 },
  logsList: { paddingHorizontal: 20 },
  logItem: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 3 },
  logHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  actionContainer: { flexDirection: 'row', alignItems: 'center' },
  actionIcon: { width: 32, height: 32, borderRadius: 8, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  actionInfo: { flex: 1 },
  actionText: { fontSize: 14, fontWeight: 'bold', color: '#111827' },
  resourceText: { fontSize: 12, color: '#6B7280' },
  timeText: { fontSize: 12, color: '#9CA3AF' },
  logContent: { marginBottom: 8 },
  userText: { fontSize: 14, color: '#6B7280', marginBottom: 4 },
  detailsText: { fontSize: 14, color: '#374151' },
  dateText: { fontSize: 12, color: '#9CA3AF', textAlign: 'right' },
  modal: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center' },
  modalContent: { backgroundColor: '#fff', borderRadius: 12, margin: 20, maxHeight: '80%', width: '90%' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 20, borderBottomWidth: 1, borderBottomColor: '#E5E7EB' },
  modalTitle: { fontSize: 18, fontWeight: 'bold', color: '#111827' },
  modalBody: { padding: 20 },
  detailRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  detailColumn: { marginBottom: 16 },
  detailLabel: { fontSize: 14, fontWeight: '600', color: '#374151', minWidth: 100 },
  detailValue: { fontSize: 14, color: '#111827', flex: 1 },
  detailValueMultiline: { fontSize: 14, color: '#111827', marginTop: 4 },
  actionBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  actionBadgeText: { fontSize: 12, fontWeight: '600' },
});

export default AuditLogScreen;