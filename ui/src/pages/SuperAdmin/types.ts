export interface Tenant {
  id: number;
  name: string;
  email: string;
  is_active: boolean;
  is_enabled?: boolean;
  count_against_license?: boolean;
  is_archived?: boolean;
  archived_at?: string | null;
  archived_by_id?: number | null;
  archive_reason?: string | null;
  created_at: string;
  user_count: number;
  subdomain?: string;
  default_currency: string;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  tenant_id: number;
  tenant_name: string;
  created_at: string;
}

export interface DatabaseStatus {
  tenant_id: number;
  tenant_name: string;
  database_name: string;
  status: string;
  message?: string;
  error?: string;
}

export interface Anomaly {
  id: number;
  tenant_id: number;
  tenant_name: string;
  entity_type: string;
  entity_id: number;
  risk_score: number;
  risk_level: string;
  reason: string;
  rule_id: string;
  details: any;
  created_at: string;
}
