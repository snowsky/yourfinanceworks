import React, { useEffect, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Filter, X } from 'lucide-react';
import { format } from 'date-fns';
import { AuditLogDetailsModal } from '@/components/audit/AuditLogDetailsModal';
import { apiRequest } from '@/lib/api';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard, ProfessionalCardContent } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalInput } from '@/components/ui/professional-input';
import {
  ProfessionalTable,
  ProfessionalTableHeader,
  ProfessionalTableBody,
  ProfessionalTableHead,
  ProfessionalTableRow,
  ProfessionalTableCell,
  StatusBadge
} from '@/components/ui/professional-table';
import { isSuperAdmin, getCurrentUser } from '@/utils/auth';
import { useOrganizations } from '@/hooks/useOrganizations';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

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
  tenant_name?: string;  // Added for all organizations view
  tenant_id?: number;    // Added for all organizations view
}

interface Organization {
  id: number;
  name: string;
}

type DateOrNull = Date | null;

export default function AuditLogPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = getCurrentUser();
  const { data: userOrganizations = [] } = useOrganizations();

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasAccess, setHasAccess] = useState(false);

  // Pagination state
  const [page, setPage] = useState(1);
  const safeSetPage = (newPage: number | ((prev: number) => number)) => {
    setPage(prev => {
      const resolvedPage = typeof newPage === 'function' ? newPage(prev) : newPage;
      return Math.max(1, resolvedPage);
    });
  };
  const [perPage, setPerPage] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // Filter state
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [status, setStatus] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [startDate, setStartDate] = useState<DateOrNull>(null);
  const [endDate, setEndDate] = useState<DateOrNull>(null);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  // Organization state for super admin
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganization, setSelectedOrganization] = useState<string>('current');
  const isCurrentUserSuperAdmin = isSuperAdmin();

  // Check permission to access audit log
  useEffect(() => {
    // Get current organization ID from localStorage
    const currentOrgId = localStorage.getItem('selected_tenant_id') || user?.tenant_id?.toString() || '';

    // Find the current organization in the user's organizations
    const currentOrg = userOrganizations.find(org => org.id.toString() === currentOrgId);

    // Check if user is admin in current organization or is a superuser
    const isAdminInCurrentOrg = currentOrg?.role === 'admin';
    const userHasAccess = isCurrentUserSuperAdmin || isAdminInCurrentOrg;

    setHasAccess(userHasAccess);

    // If user doesn't have access, redirect to home
    if (userOrganizations.length > 0 && !userHasAccess) {
      navigate('/');
    }
  }, [userOrganizations, isCurrentUserSuperAdmin, navigate, user?.tenant_id]);

  useEffect(() => {
    if (hasAccess) {
      fetchLogs(page);
    }
  }, [page, perPage, action, status, userEmail, resourceType, startDate, endDate, selectedOrganization, hasAccess]);

  // Fetch organizations for super admin
  useEffect(() => {
    if (isCurrentUserSuperAdmin && hasAccess) {
      fetchOrganizations();
    }
  }, [isCurrentUserSuperAdmin, hasAccess]);

  const fetchOrganizations = async () => {
    try {
      const data = await apiRequest<Organization[]>('/super-admin/organizations');
      setOrganizations(data);
    } catch (err: any) {
      console.error('Failed to fetch organizations:', err);
    }
  };

  const fetchLogs = async (currentPage: number = 1) => {
    // Ensure page is always positive
    if (currentPage < 1) {
      currentPage = 1;
      safeSetPage(1);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const offset = (currentPage - 1) * perPage;
      const params = new URLSearchParams();
      params.append('limit', perPage.toString());
      params.append('offset', offset.toString());

      if (search) params.append('search', search);
      if (action) params.append('action', action);
      if (status) params.append('status', status);
      if (userEmail) params.append('user_email', userEmail);
      if (resourceType) params.append('resource_type', resourceType);
      if (startDate) params.append('start_date', startDate.toISOString());
      if (endDate) params.append('end_date', endDate.toISOString());

      // Add organization_id for super admin (only for tenant endpoints, not master database)
      if (isCurrentUserSuperAdmin && selectedOrganization && selectedOrganization !== 'current') {
        // Only pass organization parameters for tenant endpoints, not for master database
        if (selectedOrganization !== 'master') {
          if (selectedOrganization === 'all') {
            params.append('all_organizations', 'true');
          } else {
            // Only pass organization_id for specific tenant organizations
            params.append('organization_id', selectedOrganization);
          }
        }
      }

      // Use master audit log endpoint for super admins when viewing master database operations
      // Use regular endpoint with all_organizations=true for viewing all tenant logs
      const endpoint = isCurrentUserSuperAdmin && selectedOrganization === 'master' 
        ? '/audit-logs/master-list'
        : '/audit-logs';

      const data = await apiRequest<{
        audit_logs: AuditLog[],
        total: number,
        page: number,
        per_page: number,
        total_pages: number
      }>(`${endpoint}?${params.toString()}`);

      setLogs(data.audit_logs || []);
      setTotalCount(data.total || 0);
      setTotalPages(data.total_pages || 0);
    } catch (err: any) {
      setError(err.message || 'Error');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    safeSetPage(1);
    fetchLogs(1);
  };

  // Extract unique values for dropdowns (these will now be based on the current page's results)
  // In a more robust implementation, these would come from separate metadata endpoints
  const actions = useMemo(() => Array.from(new Set(logs.map(l => l.action).filter(Boolean))), [logs]);
  const statuses = useMemo(() => Array.from(new Set(logs.map(l => l.status).filter(Boolean))), [logs]);
  const users = useMemo(() => Array.from(new Set(logs.map(l => l.user_email).filter(Boolean))), [logs]);
  const resourceTypes = useMemo(() => Array.from(new Set(logs.map(l => l.resource_type).filter(Boolean))), [logs]);

  const clearFilters = () => {
    setSearch('');
    setAction('');
    setStatus('');
    setUserEmail('');
    setResourceType('');
    setStartDate(null);
    setEndDate(null);
    setSelectedOrganization('current');
    safeSetPage(1);
    // Directly fetch with cleared search too
    fetchLogs(1);
  };

  // Helper to convert resource_type to camelCase
  function toCamelCase(str: string) {
    if (!str) return '';
    // If the string is all lowercase or all uppercase and has no underscores, capitalize only the first letter and lowercase the rest
    if (/^[a-z]+$/.test(str) || /^[A-Z]+$/.test(str)) {
      return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }
    // Otherwise, convert snake_case to camelCase
    return str.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
  }

  const getStatusBadge = (status: string) => {
    const success = ['success', 'completed', 'verified', 'active'];
    const warning = ['pending', 'processing', 'warning'];
    const danger = ['failed', 'error', 'deleted', 'banned'];

    let variant: 'success' | 'warning' | 'danger' | 'neutral' = 'neutral';

    if (success.some(s => status.toLowerCase().includes(s))) variant = 'success';
    else if (warning.some(s => status.toLowerCase().includes(s))) variant = 'warning';
    else if (danger.some(s => status.toLowerCase().includes(s))) variant = 'danger';

    return (
      <StatusBadge status={variant} variant="outline">
        {toCamelCase(status)}
      </StatusBadge>
    );
  };

  const getActionBadge = (action: string) => {
    const create = ['create', 'add', 'insert', 'upload'];
    const update = ['update', 'edit', 'modify', 'change'];
    const deleteAction = ['delete', 'remove', 'destroy'];

    let variant: 'success' | 'warning' | 'danger' | 'neutral' = 'neutral';

    if (create.some(s => action.toLowerCase().includes(s))) variant = 'success';
    else if (update.some(s => action.toLowerCase().includes(s))) variant = 'warning';
    else if (deleteAction.some(s => action.toLowerCase().includes(s))) variant = 'danger';

    return (
      <StatusBadge status={variant} variant="subtle">
        {toCamelCase(action)}
      </StatusBadge>
    );
  };

  return (
    <div className="h-full space-y-8 p-8 fade-in">
      <PageHeader
        title={t('navigation.audit_log')}
        description={t('auditLog.description')}
      />

      <div className="flex flex-col space-y-4">
        <div className="flex flex-wrap gap-2 items-center">
          <form onSubmit={handleSearch} className="flex gap-2">
            <ProfessionalInput
              placeholder={t('common.search') || 'Search...'}
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="max-w-xs"
              inputSize="sm"
            />
            <ProfessionalButton type="submit" variant="secondary" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              {t('common.filter') || 'Filter'}
            </ProfessionalButton>
          </form>

          <Select value={perPage.toString()} onValueChange={v => {
            setPerPage(parseInt(v));
            safeSetPage(1);
          }}>
            <SelectTrigger className="w-[140px] bg-background/50 border-border/50">
              <SelectValue placeholder="Per page" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="25">25 per page</SelectItem>
              <SelectItem value="50">50 per page</SelectItem>
              <SelectItem value="100">100 per page</SelectItem>
              <SelectItem value="500">500 per page</SelectItem>
              <SelectItem value="10000">Load All</SelectItem>
            </SelectContent>
          </Select>

          <Select value={action || 'all'} onValueChange={v => {
            setAction(v === 'all' ? '' : v);
            safeSetPage(1);
          }}>
            <SelectTrigger className="w-[160px] bg-background/50 border-border/50">
              <SelectValue placeholder={t('auditLog.filters.action') || 'Action'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_actions') || 'All Actions'}</SelectItem>
              {actions.map(a => (
                <SelectItem key={a} value={a}>{toCamelCase(a)}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={status || 'all'} onValueChange={v => {
            setStatus(v === 'all' ? '' : v);
            safeSetPage(1);
          }}>
            <SelectTrigger className="w-[140px] bg-background/50 border-border/50">
              <SelectValue placeholder={t('auditLog.filters.status') || 'Status'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_statuses') || 'All Statuses'}</SelectItem>
              {statuses.map(s => (
                <SelectItem key={s} value={s}>{toCamelCase(s)}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={userEmail || 'all'} onValueChange={v => {
            setUserEmail(v === 'all' ? '' : v);
            safeSetPage(1);
          }}>
            <SelectTrigger className="w-[200px] bg-background/50 border-border/50">
              <SelectValue placeholder={t('auditLog.filters.user') || 'User'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_users') || 'All Users'}</SelectItem>
              {users.map(u => (
                <SelectItem key={u} value={u}>{u}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={resourceType || 'all'} onValueChange={v => {
            setResourceType(v === 'all' ? '' : v);
            safeSetPage(1);
          }}>
            <SelectTrigger className="w-[180px] bg-background/50 border-border/50">
              <SelectValue placeholder={t('auditLog.filters.resource_type') || 'Resource Type'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('auditLog.filters.all_resources') || 'All Resources'}</SelectItem>
              {resourceTypes.map(r => (
                <SelectItem key={r} value={r}>{toCamelCase(r)}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isCurrentUserSuperAdmin && (
            <Select value={selectedOrganization} onValueChange={v => {
              setSelectedOrganization(v);
              safeSetPage(1);
            }}>
              <SelectTrigger className="w-[240px] bg-background/50 border-border/50">
                <SelectValue placeholder="Select Organization" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="current">Current Organization</SelectItem>
                <SelectItem value="master" className="text-purple-600">
                  Master Database (Super Admin Operations)
                </SelectItem>
                <SelectItem value="all" className="text-orange-600">
                  All Organizations (Slow)
                </SelectItem>
                {organizations.map(org => (
                  <SelectItem key={org.id} value={org.id.toString()}>
                    {org.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Popover>
            <PopoverTrigger asChild>
              <ProfessionalButton variant="outline" size="sm" className="flex items-center gap-2 border-border/50">
                <CalendarIcon className="h-4 w-4" />
                {startDate ? format(startDate, 'PPP') : t('auditLog.filters.start_date') || 'Start Date'}
              </ProfessionalButton>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={startDate}
                onSelect={(date) => {
                  setStartDate(date);
                  safeSetPage(1);
                }}
                initialFocus
              />
            </PopoverContent>
          </Popover>

          <Popover>
            <PopoverTrigger asChild>
              <ProfessionalButton variant="outline" size="sm" className="flex items-center gap-2 border-border/50">
                <CalendarIcon className="h-4 w-4" />
                {endDate ? format(endDate, 'PPP') : t('auditLog.filters.end_date') || 'End Date'}
              </ProfessionalButton>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={endDate}
                onSelect={(date) => {
                  setEndDate(date);
                  safeSetPage(1);
                }}
                initialFocus
              />
            </PopoverContent>
          </Popover>

          <ProfessionalButton variant="ghost" size="sm" onClick={clearFilters} className="flex items-center gap-2">
            <X className="h-4 w-4" />
            {t('common.clear') || 'Clear'}
          </ProfessionalButton>

          <ProfessionalButton onClick={() => fetchLogs(page)} disabled={loading} size="sm" variant="outline">
            {t('auditLog.reload') || 'Reload'}
          </ProfessionalButton>
        </div>

        {error && <div className="text-destructive mb-2 text-sm text-center">{error}</div>}

        <ProfessionalCard className="slide-in" variant="elevated">
          <ProfessionalCardContent className="p-0">
            <ProfessionalTable>
              <ProfessionalTableHeader>
                <ProfessionalTableRow>
                  <ProfessionalTableHead>ID</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('auditLog.filters.user') || 'User'}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('auditLog.filters.action') || 'Action'}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('auditLog.filters.resource_type') || 'Resource Type'}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('auditLog.filters.status') || 'Status'}</ProfessionalTableHead>
                  {isCurrentUserSuperAdmin && (selectedOrganization === 'all' || selectedOrganization === 'master') && (
                    <ProfessionalTableHead>Organization</ProfessionalTableHead>
                  )}
                  <ProfessionalTableHead>{t('auditLog.filters.date') || 'Date'}</ProfessionalTableHead>
                </ProfessionalTableRow>
              </ProfessionalTableHeader>
              <ProfessionalTableBody>
                {loading ? (
                  <ProfessionalTableRow>
                    <ProfessionalTableCell colSpan={isCurrentUserSuperAdmin && (selectedOrganization === 'all' || selectedOrganization === 'master') ? 7 : 6} className="h-24 text-center text-muted-foreground">
                      {t('common.loading') || 'Loading...'}
                    </ProfessionalTableCell>
                  </ProfessionalTableRow>
                ) : logs.length === 0 ? (
                  <ProfessionalTableRow>
                    <ProfessionalTableCell colSpan={isCurrentUserSuperAdmin && (selectedOrganization === 'all' || selectedOrganization === 'master') ? 7 : 6} className="h-24 text-center text-muted-foreground">
                      {t('common.no_results') || 'No audit logs found'}
                    </ProfessionalTableCell>
                  </ProfessionalTableRow>
                ) : (
                  logs.map(log => (
                    <ProfessionalTableRow
                      key={log.id}
                      className="cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => setSelectedLog(log)}
                    >
                      <ProfessionalTableCell className="font-mono">{log.id}</ProfessionalTableCell>
                      <ProfessionalTableCell>{log.user_email}</ProfessionalTableCell>
                      <ProfessionalTableCell>{getActionBadge(log.action)}</ProfessionalTableCell>
                      <ProfessionalTableCell><span className="text-muted-foreground">{toCamelCase(log.resource_type)}</span></ProfessionalTableCell>
                      <ProfessionalTableCell>{getStatusBadge(log.status)}</ProfessionalTableCell>
                      {isCurrentUserSuperAdmin && (selectedOrganization === 'all' || selectedOrganization === 'master') && (
                        <ProfessionalTableCell>
                          {selectedOrganization === 'master' 
                            ? (log.tenant_name || 'Master Database') 
                            : (log.tenant_name || 'Unknown')
                          }
                        </ProfessionalTableCell>
                      )}
                      <ProfessionalTableCell className="text-muted-foreground">{new Date(log.created_at).toLocaleString()}</ProfessionalTableCell>
                    </ProfessionalTableRow>
                  ))
                )}
              </ProfessionalTableBody>
            </ProfessionalTable>

            <div className="py-4 px-6 flex items-center justify-between gap-4 border-t border-border/50">
              <div className="text-muted-foreground whitespace-nowrap">
                {t('auditLog.total_logs', { count: totalCount })}
              </div>
              {totalCount > 0 && (
                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        onClick={() => safeSetPage(p => Math.max(1, p - 1))}
                        className={page === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                      />
                    </PaginationItem>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum = page;
                      if (totalPages <= 5) pageNum = i + 1;
                      else if (page <= 3) pageNum = i + 1;
                      else if (page >= totalPages - 2) pageNum = totalPages - 4 + i;
                      else pageNum = page - 2 + i;

                      return (
                        <PaginationItem key={pageNum}>
                          <PaginationLink
                            onClick={() => safeSetPage(pageNum)}
                            isActive={page === pageNum}
                            className="cursor-pointer"
                          >
                            {pageNum}
                          </PaginationLink>
                        </PaginationItem>
                      );
                    })}
                    <PaginationItem>
                      <PaginationNext
                        onClick={() => safeSetPage(p => Math.min(totalPages, p + 1))}
                        className={page === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              )}
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>

        <AuditLogDetailsModal
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
          auditLog={selectedLog}
        />
      </div>
    </div>
  );
} 