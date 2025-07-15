import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Trash2, Edit, UserPlus, Building, Database, Users, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { toast } from 'sonner';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarProvider } from '@/components/ui/sidebar';

interface Tenant {
  id: number;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  user_count: number;
  subdomain?: string;
  default_currency: string;
}

interface User {
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

interface DatabaseStatus {
  tenant_id: number;
  tenant_name: string;
  database_name: string;
  status: string;
  message?: string;
  error?: string;
}

const SuperAdminDashboard: React.FC = () => {
  const { user } = useAuth();

  // Check if user is super admin BEFORE any hooks are called
  if (!user?.is_superuser) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Alert className="max-w-md">
          <ShieldCheck className="h-4 w-4" />
          <AlertDescription>
            You need super admin access to view this page.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return <SuperAdminDashboardContent user={user} />;
};

// Separate component for the main dashboard content
const SuperAdminDashboardContent: React.FC<{ user: any }> = ({ user }) => {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [databases, setDatabases] = useState<DatabaseStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('tenants');
  
  // Form states
  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [createTenantForm, setCreateTenantForm] = useState({
    name: '',
    email: '',
    default_currency: 'USD'
  });
  const [createUserForm, setCreateUserForm] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: 'user',
    password: '',
    tenant_id: ''
  });

  // Add state for promote form
  const [promoteEmail, setPromoteEmail] = useState('');
  const [promoteLoading, setPromoteLoading] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  // --- Add state for edit modals ---
  const [editTenant, setEditTenant] = useState<Tenant | null>(null);
  const [editTenantForm, setEditTenantForm] = useState({ name: '', email: '', default_currency: 'USD' });
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editUserForm, setEditUserForm] = useState({ first_name: '', last_name: '', email: '', role: 'user', password: '' });

  // --- Add state for delete confirmation dialogs ---
  const [tenantToDelete, setTenantToDelete] = useState<Tenant | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  // Add state for recreate database confirmation
  const [dbToRecreate, setDbToRecreate] = useState<DatabaseStatus | null>(null);

  const fetchTenants = async () => {
    try {
      const response = await fetch('/api/v1/super-admin/tenants', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to fetch tenants');
      const data = await response.json();
      setTenants(data);
    } catch (err) {
      setError('Failed to fetch tenants');
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/v1/super-admin/users', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to fetch users');
      const data = await response.json();
      setUsers(data);
    } catch (err) {
      setError('Failed to fetch users');
    }
  };

  const fetchDatabaseOverview = async () => {
    try {
      const response = await fetch('/api/v1/super-admin/database/overview', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to fetch database overview');
      const data = await response.json();
      setDatabases(data.databases || []);
    } catch (err) {
      setError('Failed to fetch database overview');
    }
  };

  const handleCreateTenant = async () => {
    try {
      const response = await fetch('/api/v1/super-admin/tenants', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(createTenantForm)
      });
      
      if (!response.ok) throw new Error('Failed to create tenant');
      
      setShowCreateTenant(false);
      setCreateTenantForm({ name: '', email: '', default_currency: 'USD' });
      fetchTenants();
    } catch (err) {
      setError('Failed to create tenant');
    }
  };

  const handleCreateUser = async () => {
    try {
      const response = await fetch(`/api/v1/super-admin/users?tenant_id=${createUserForm.tenant_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(createUserForm)
      });
      
      if (!response.ok) throw new Error('Failed to create user');
      
      setShowCreateUser(false);
      setCreateUserForm({ email: '', first_name: '', last_name: '', role: 'user', password: '', tenant_id: '' });
      fetchUsers();
    } catch (err) {
      setError('Failed to create user');
    }
  };

  // --- Updated Delete Tenant Handler ---
  const handleDeleteTenant = (tenant: Tenant) => {
    setTenantToDelete(tenant);
  };
  const confirmDeleteTenant = async () => {
    if (!tenantToDelete) return;
    try {
      const response = await fetch(`/api/v1/super-admin/tenants/${tenantToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to delete tenant');
      toast.success('Tenant deleted successfully');
      setTenantToDelete(null);
      // Remove tenant from state
      setTenants(prev => prev.filter(t => t.id !== tenantToDelete.id));
      // Refresh users and databases lists
      fetchUsers();
      fetchDatabaseOverview();
    } catch (err) {
      toast.error('Failed to delete tenant');
      setTenantToDelete(null);
    }
  };

  // --- Updated Delete User Handler ---
  const handleDeleteUser = (user: User) => {
    setUserToDelete(user);
  };
  const confirmDeleteUser = async () => {
    if (!userToDelete) return;
    try {
      const response = await fetch(`/api/v1/super-admin/users/${userToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to delete user');
      toast.success('User deleted successfully');
      setUserToDelete(null);
      fetchUsers();
    } catch (err) {
      toast.error('Failed to delete user');
      setUserToDelete(null);
    }
  };

  const handleRecreateDatabase = (db: DatabaseStatus) => {
    setDbToRecreate(db);
  };
  const confirmRecreateDatabase = async () => {
    if (!dbToRecreate) return;
    try {
      const response = await fetch(`/api/v1/super-admin/tenants/${dbToRecreate.tenant_id}/database/recreate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      if (!response.ok) throw new Error('Failed to recreate database');
      toast.success('Database recreated successfully');
      setDbToRecreate(null);
      fetchDatabaseOverview();
    } catch (err) {
      toast.error('Failed to recreate database');
      setDbToRecreate(null);
    }
  };

  const handlePromote = async (e: React.FormEvent) => {
    e.preventDefault();
    setPromoteLoading(true);
    setPromoteError(null);
    try {
      const response = await fetch('/api/v1/super-admin/promote', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ email: promoteEmail })
      });
      let data: any = {};
      try {
        data = await response.json();
      } catch {}
      if (response.ok) {
        toast.success(data.message || 'User promoted to super admin!');
        setPromoteEmail('');
        setPromoteError(null);
        fetchUsers();
      } else {
        const errorMsg =
          (response.status === 404 && 'User does not exist') ||
          data.detail ||
          data.message ||
          'Failed to promote user';
        setPromoteError(errorMsg);
      }
    } catch (err) {
      setPromoteError('Failed to promote user');
    } finally {
      setPromoteLoading(false);
    }
  };

  // --- Edit Tenant Handler ---
  const handleEditTenant = (tenant: Tenant) => {
    setEditTenant(tenant);
    setEditTenantForm({
      name: tenant.name,
      email: tenant.email,
      default_currency: tenant.default_currency || 'USD',
    });
  };
  const handleUpdateTenant = async () => {
    if (!editTenant) return;
    try {
      const response = await fetch(`/api/v1/super-admin/tenants/${editTenant.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(editTenantForm)
      });
      if (!response.ok) throw new Error('Failed to update tenant');
      setEditTenant(null);
      toast.success('Tenant updated successfully');
      fetchTenants();
    } catch (err) {
      toast.error('Failed to update tenant');
    }
  };

  // --- Edit User Handler ---
  const handleEditUser = (user: User) => {
    setEditUser(user);
    setEditUserForm({
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      role: user.role,
      password: ''
    });
  };
  const handleUpdateUser = async () => {
    if (!editUser) return;
    try {
      const response = await fetch(`/api/v1/super-admin/users/${editUser.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(editUserForm)
      });
      if (!response.ok) throw new Error('Failed to update user');
      setEditUser(null);
      toast.success('User updated successfully');
      fetchUsers();
    } catch (err) {
      toast.error('Failed to update user');
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchTenants(), fetchUsers(), fetchDatabaseOverview()]);
      setLoading(false);
    };
    
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading super admin dashboard...</p>
        </div>
      </div>
    );
  }

  const totalUsers = users.length;
  const activeTenants = tenants.filter(t => t.is_active).length;
  const healthyDatabases = databases.filter(db => db.status === 'connected').length;
  const superUsers = users.filter(u => u.is_superuser).length;
  const unhealthyDatabases = databases.filter(db => db.status !== 'connected');
  const systemHealthy = unhealthyDatabases.length === 0;

  // Find tenants whose email does not exist in the users list
  const tenantEmailsMissingUsers = tenants.filter(
    t => t.email && !users.some(u => u.email === t.email)
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Alert for tenants whose email is missing in users */}
        {tenantEmailsMissingUsers.length > 0 && (
          <Alert className="mb-6" variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <b>Warning:</b> The following tenant email(s) do not exist as users:<br />
              <ul className="list-disc ml-6 mt-2">
                {tenantEmailsMissingUsers.map(t => (
                  <li key={t.id}>
                    <b>{t.name}</b>: <span className="text-red-600">{t.email}</span>
                  </li>
                ))}
              </ul>
              Please create a user with the same email if you want tenant admins to be able to log in.
            </AlertDescription>
          </Alert>
        )}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Super Admin Dashboard</h1>
          <p className="text-gray-600">Manage all tenants, users, and databases</p>
        </div>

        {error && (
          <Alert className="mb-6" variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mb-8">
          <Card>
            <CardContent className="p-6">
              <form onSubmit={handlePromote} className="flex flex-col md:flex-row items-center gap-4">
                <Label htmlFor="promote-email" className="font-medium">Promote User to Super Admin:</Label>
                <Input
                  id="promote-email"
                  type="email"
                  placeholder="Enter user email"
                  value={promoteEmail}
                  onChange={e => {
                    setPromoteEmail(e.target.value);
                    setPromoteError(null);
                  }}
                  className="max-w-xs"
                  required
                />
                <Button type="submit" disabled={promoteLoading || !promoteEmail}>
                  {promoteLoading ? 'Promoting...' : 'Promote'}
                </Button>
                {promoteError && (
                  <div className="text-red-600 text-sm mt-2" role="alert">{promoteError}</div>
                )}
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Total Tenants</p>
                  <p className="text-2xl font-bold">{tenants.length}</p>
                </div>
                <Building className="h-8 w-8 text-blue-500" />
              </div>
              <p className="text-sm text-gray-500 mt-2">{activeTenants} active</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Total Users</p>
                  <p className="text-2xl font-bold">{totalUsers}</p>
                </div>
                <Users className="h-8 w-8 text-green-500" />
              </div>
              <p className="text-sm text-gray-500 mt-2">{superUsers} super users</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">Databases</p>
                  <p className="text-2xl font-bold">{databases.length}</p>
                </div>
                <Database className="h-8 w-8 text-purple-500" />
              </div>
              <p className="text-sm text-gray-500 mt-2">{healthyDatabases} healthy</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">System Status</p>
                  <p className={`text-2xl font-bold ${systemHealthy ? 'text-green-600' : 'text-red-600'}`}>
                    {systemHealthy ? 'All systems operational' : `${unhealthyDatabases.length} issue${unhealthyDatabases.length > 1 ? 's' : ''} detected`}
                  </p>
                </div>
                {systemHealthy ? (
                  <ShieldCheck className="h-8 w-8 text-green-500" />
                ) : (
                  <AlertTriangle className="h-8 w-8 text-red-500" />
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="tenants">Tenants</TabsTrigger>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="databases">Databases</TabsTrigger>
          </TabsList>
          
          <TabsContent value="tenants" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle>Tenants Management</CardTitle>
                  <Dialog open={showCreateTenant} onOpenChange={setShowCreateTenant}>
                    <DialogTrigger asChild>
                      <Button>
                        <Building className="h-4 w-4 mr-2" />
                        Create Tenant
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Tenant</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="tenant-name">Organization Name</Label>
                          <Input
                            id="tenant-name"
                            value={createTenantForm.name}
                            onChange={(e) => setCreateTenantForm(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="Enter organization name"
                          />
                        </div>
                        <div>
                          <Label htmlFor="tenant-email">Email</Label>
                          <Input
                            id="tenant-email"
                            type="email"
                            value={createTenantForm.email}
                            onChange={(e) => setCreateTenantForm(prev => ({ ...prev, email: e.target.value }))}
                            placeholder="Enter email"
                          />
                        </div>
                        <div>
                          <Label htmlFor="tenant-currency">Default Currency</Label>
                          <Select value={createTenantForm.default_currency} onValueChange={(value) => setCreateTenantForm(prev => ({ ...prev, default_currency: value }))}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="USD">USD</SelectItem>
                              <SelectItem value="EUR">EUR</SelectItem>
                              <SelectItem value="GBP">GBP</SelectItem>
                              <SelectItem value="JPY">JPY</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <Button onClick={handleCreateTenant} className="w-full">Create Tenant</Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Users</TableHead>
                      <TableHead>Currency</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tenants
                      .slice()
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((tenant) => (
                        <TableRow key={tenant.id}>
                          <TableCell className="font-medium">{tenant.name}</TableCell>
                          <TableCell>{tenant.email}</TableCell>
                          <TableCell>{tenant.user_count}</TableCell>
                          <TableCell>{tenant.default_currency}</TableCell>
                          <TableCell>
                            <Badge variant={tenant.is_active ? "default" : "secondary"}>
                              {tenant.is_active ? 'Active' : 'Inactive'}
                            </Badge>
                          </TableCell>
                          <TableCell>{new Date(tenant.created_at).toLocaleDateString()}</TableCell>
                          <TableCell>
                            <div className="flex space-x-2">
                              <Button size="sm" variant="outline" onClick={() => handleEditTenant(tenant)}>
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => handleDeleteTenant(tenant)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="users" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle>Users Management</CardTitle>
                  <Dialog open={showCreateUser} onOpenChange={setShowCreateUser}>
                    <DialogTrigger asChild>
                      <Button>
                        <UserPlus className="h-4 w-4 mr-2" />
                        Create User
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New User</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="user-email">Email</Label>
                          <Input
                            id="user-email"
                            type="email"
                            value={createUserForm.email}
                            onChange={(e) => setCreateUserForm(prev => ({ ...prev, email: e.target.value }))}
                            placeholder="Enter email"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label htmlFor="user-first-name">First Name</Label>
                            <Input
                              id="user-first-name"
                              value={createUserForm.first_name}
                              onChange={(e) => setCreateUserForm(prev => ({ ...prev, first_name: e.target.value }))}
                              placeholder="First name"
                            />
                          </div>
                          <div>
                            <Label htmlFor="user-last-name">Last Name</Label>
                            <Input
                              id="user-last-name"
                              value={createUserForm.last_name}
                              onChange={(e) => setCreateUserForm(prev => ({ ...prev, last_name: e.target.value }))}
                              placeholder="Last name"
                            />
                          </div>
                        </div>
                        <div>
                          <Label htmlFor="user-tenant">Tenant</Label>
                          <Select value={createUserForm.tenant_id} onValueChange={(value) => setCreateUserForm(prev => ({ ...prev, tenant_id: value }))}>
                            <SelectTrigger>
                              <SelectValue placeholder="Select tenant" />
                            </SelectTrigger>
                            <SelectContent>
                              {tenants.map(tenant => (
                                <SelectItem key={tenant.id} value={tenant.id.toString()}>
                                  {tenant.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label htmlFor="user-role">Role</Label>
                          <Select value={createUserForm.role} onValueChange={(value) => setCreateUserForm(prev => ({ ...prev, role: value }))}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="admin">Admin</SelectItem>
                              <SelectItem value="user">User</SelectItem>
                              <SelectItem value="viewer">Viewer</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label htmlFor="user-password">Password</Label>
                          <Input
                            id="user-password"
                            type="password"
                            value={createUserForm.password}
                            onChange={(e) => setCreateUserForm(prev => ({ ...prev, password: e.target.value }))}
                            placeholder="Enter password"
                          />
                        </div>
                        <Button onClick={handleCreateUser} className="w-full">Create User</Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Tenant</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">
                          {user.first_name} {user.last_name}
                          {user.is_superuser && (
                            <Badge variant="outline" className="ml-2">Super</Badge>
                          )}
                        </TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{user.tenant_name}</TableCell>
                        <TableCell>
                          <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                            {user.role}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={user.is_active ? "default" : "secondary"}>
                            {user.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell>{new Date(user.created_at).toLocaleDateString()}</TableCell>
                        <TableCell>
                          <div className="flex space-x-2">
                            <Button size="sm" variant="outline" onClick={() => handleEditUser(user)}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => handleDeleteUser(user)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="databases" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Database Management</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tenant</TableHead>
                      <TableHead>Database</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {databases.map((db) => (
                      <TableRow key={db.tenant_id}>
                        <TableCell className="font-medium">{db.tenant_name}</TableCell>
                        <TableCell>{db.database_name}</TableCell>
                        <TableCell>
                          <Badge variant={db.status === 'connected' ? 'default' : 'destructive'}>
                            {db.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{db.message || db.error || '-'}</TableCell>
                        <TableCell>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleRecreateDatabase(db)}
                          >
                            <Database className="h-4 w-4 mr-2" />
                            Recreate
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Edit Tenant Dialog */}
      <Dialog open={!!editTenant} onOpenChange={open => { if (!open) setEditTenant(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-tenant-name">Organization Name</Label>
              <Input id="edit-tenant-name" value={editTenantForm.name} onChange={e => setEditTenantForm(prev => ({ ...prev, name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-tenant-email">Email</Label>
              <Input id="edit-tenant-email" type="email" value={editTenantForm.email} onChange={e => setEditTenantForm(prev => ({ ...prev, email: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-tenant-currency">Default Currency</Label>
              <Select value={editTenantForm.default_currency} onValueChange={value => setEditTenantForm(prev => ({ ...prev, default_currency: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                  <SelectItem value="JPY">JPY</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handleUpdateTenant} className="w-full">Update Tenant</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={!!editUser} onOpenChange={open => { if (!open) setEditUser(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-user-first-name">First Name</Label>
              <Input id="edit-user-first-name" value={editUserForm.first_name} onChange={e => setEditUserForm(prev => ({ ...prev, first_name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-user-last-name">Last Name</Label>
              <Input id="edit-user-last-name" value={editUserForm.last_name} onChange={e => setEditUserForm(prev => ({ ...prev, last_name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-user-email">Email</Label>
              <Input id="edit-user-email" type="email" value={editUserForm.email} onChange={e => setEditUserForm(prev => ({ ...prev, email: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-user-role">Role</Label>
              <Select value={editUserForm.role} onValueChange={value => setEditUserForm(prev => ({ ...prev, role: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="edit-user-password">Password (leave blank to keep unchanged)</Label>
              <Input id="edit-user-password" type="password" value={editUserForm.password} onChange={e => setEditUserForm(prev => ({ ...prev, password: e.target.value }))} />
            </div>
            <Button onClick={handleUpdateUser} className="w-full">Update User</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Tenant Confirmation Dialog */}
      <Dialog open={!!tenantToDelete} onOpenChange={open => { if (!open) setTenantToDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>Are you sure you want to delete tenant <b>{tenantToDelete?.name}</b>? This will delete all associated data.</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setTenantToDelete(null)}>Cancel</Button>
              <Button variant="destructive" onClick={confirmDeleteTenant}>Delete</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete User Confirmation Dialog */}
      <Dialog open={!!userToDelete} onOpenChange={open => { if (!open) setUserToDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>Are you sure you want to delete user <b>{userToDelete?.email}</b>?</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setUserToDelete(null)}>Cancel</Button>
              <Button variant="destructive" onClick={confirmDeleteUser}>Delete</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Recreate Database Confirmation Dialog */}
      <Dialog open={!!dbToRecreate} onOpenChange={open => { if (!open) setDbToRecreate(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Recreate Database</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>Are you sure you want to recreate the database for tenant <b>{dbToRecreate?.tenant_name}</b>? This will <span className="text-red-600 font-bold">DELETE ALL DATA</span> for this tenant.</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDbToRecreate(null)}>Cancel</Button>
              <Button variant="destructive" onClick={confirmRecreateDatabase}>Recreate</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default function SuperAdminDashboardPage() {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen">
        <div className="w-64 flex-shrink-0">
          <AppSidebar />
        </div>
        <div className="flex-1">
          <SuperAdminDashboard />
        </div>
      </div>
    </SidebarProvider>
  );
} 