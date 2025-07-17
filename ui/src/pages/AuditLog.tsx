import React, { useEffect, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Filter, X } from 'lucide-react';
import { format } from 'date-fns';
import { API_BASE_URL } from '@/lib/api';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { AuditLogDetailsModal } from '@/components/audit/AuditLogDetailsModal';
import { AppLayout } from '@/components/layout/AppLayout';
import { apiRequest } from '@/lib/api';

interface AuditLog {
  id: number;
  user_id: number;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  resource_name?: string;
  details?: any;
  ip_address?: string;
  user_agent?: string;
  status: string;
  error_message?: string;
  created_at: string;
}

type DateOrNull = Date | null;

export default function AuditLogPage() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [status, setStatus] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [startDate, setStartDate] = useState<DateOrNull>(null);
  const [endDate, setEndDate] = useState<DateOrNull>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      // Use apiRequest to ensure headers are set
      const data = await apiRequest<{ audit_logs: AuditLog[] }>('/audit-logs?limit=1000');
      setLogs(data.audit_logs || []);
    } catch (err: any) {
      setError(err.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  // Extract unique values for dropdowns
  const actions = useMemo(() => Array.from(new Set(logs.map(l => l.action).filter(Boolean))), [logs]);
  const statuses = useMemo(() => Array.from(new Set(logs.map(l => l.status).filter(Boolean))), [logs]);
  const users = useMemo(() => Array.from(new Set(logs.map(l => l.user_email).filter(Boolean))), [logs]);
  const resourceTypes = useMemo(() => Array.from(new Set(logs.map(l => l.resource_type).filter(Boolean))), [logs]);

  // Filtering logic
  const filteredLogs = logs.filter(log => {
    if (search && !(
      log.user_email.toLowerCase().includes(search.toLowerCase()) ||
      log.action.toLowerCase().includes(search.toLowerCase()) ||
      log.resource_type.toLowerCase().includes(search.toLowerCase()) ||
      (log.resource_name && log.resource_name.toLowerCase().includes(search.toLowerCase())) ||
      (log.details && JSON.stringify(log.details).toLowerCase().includes(search.toLowerCase()))
    )) return false;
    if (action && log.action !== action) return false;
    if (status && log.status !== status) return false;
    if (userEmail && log.user_email !== userEmail) return false;
    if (resourceType && log.resource_type !== resourceType) return false;
    if (startDate && new Date(log.created_at) < startDate) return false;
    if (endDate && new Date(log.created_at) > endDate) return false;
    return true;
  });

  const clearFilters = () => {
    setSearch('');
    setAction('');
    setStatus('');
    setUserEmail('');
    setResourceType('');
    setStartDate(null);
    setEndDate(null);
  };

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-bold mb-4">{t('navigation.audit_log')}</h1>
        <div className="mb-4 flex flex-wrap gap-2 items-center">
          <Input
            placeholder={t('common.search') || 'Search...'}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="max-w-xs"
          />
          <Select value={action || 'all'} onValueChange={v => setAction(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder={t('auditLog.filters.action') || 'Action'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_actions') || 'All Actions'}</SelectItem>
              {actions.map(a => (
                <SelectItem key={a} value={a}>{a}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status || 'all'} onValueChange={v => setStatus(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder={t('auditLog.filters.status') || 'Status'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_statuses') || 'All Statuses'}</SelectItem>
              {statuses.map(s => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={userEmail || 'all'} onValueChange={v => setUserEmail(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={t('auditLog.filters.user') || 'User'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_users') || 'All Users'}</SelectItem>
              {users.map(u => (
                <SelectItem key={u} value={u}>{u}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={resourceType || 'all'} onValueChange={v => setResourceType(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={t('auditLog.filters.resource_type') || 'Resource Type'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_resources') || 'All Resources'}</SelectItem>
              {resourceTypes.map(r => (
                <SelectItem key={r} value={r}>{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="flex items-center gap-2">
                <CalendarIcon className="h-4 w-4" />
                {startDate ? format(startDate, 'PPP') : t('auditLog.filters.start_date') || 'Start Date'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={startDate}
                onSelect={setStartDate}
                initialFocus
              />
            </PopoverContent>
          </Popover>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="flex items-center gap-2">
                <CalendarIcon className="h-4 w-4" />
                {endDate ? format(endDate, 'PPP') : t('auditLog.filters.end_date') || 'End Date'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={endDate}
                onSelect={setEndDate}
                initialFocus
              />
            </PopoverContent>
          </Popover>
          <Button variant="ghost" size="sm" onClick={clearFilters} className="flex items-center gap-2">
            <X className="h-4 w-4" />
            {t('common.clear') || 'Clear'}
          </Button>
          <Button onClick={fetchLogs} disabled={loading}>
            {t('auditLog.reload') || 'Reload'}
          </Button>
        </div>
        {error && <div className="text-red-500 mb-2">{error}</div>}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredLogs.map(log => (
                <TableRow key={log.id} className="cursor-pointer hover:bg-muted/50" onClick={() => setSelectedLog(log)}>
                  <TableCell>{log.id}</TableCell>
                  <TableCell>{log.user_email}</TableCell>
                  <TableCell>{log.action}</TableCell>
                  <TableCell>{log.resource_type} {log.resource_id}</TableCell>
                  <TableCell>{log.status}</TableCell>
                  <TableCell>{new Date(log.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <AuditLogDetailsModal
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
          auditLog={selectedLog}
        />
      </div>
    </AppLayout>
  );
} 