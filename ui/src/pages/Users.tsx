import React, { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { api, superAdminApi, userApi } from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger
} from "@/components/ui/dialog";
import { Loader2, Plus } from "lucide-react";
import { useTranslation } from 'react-i18next';
import { getErrorMessage } from '@/lib/api';
import { JoinRequestsTable } from '@/components/JoinRequestsTable';

const ROLES = ["admin", "user", "viewer"];

type User = {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

type Invite = {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  role: string;
  is_accepted: boolean;
  expires_at: string;
  created_at: string;
  invited_by?: string;
};



export default function UsersPage() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
    role: "user",
  });
  const [inviting, setInviting] = useState(false);
  const [activationDialogOpen, setActivationDialogOpen] = useState(false);
  const [activationInvite, setActivationInvite] = useState<Invite | null>(null);
  const [activationForm, setActivationForm] = useState({
    password: "",
    first_name: "",
    last_name: "",
  });
  const [activating, setActivating] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // User management states
  const [togglingStatus, setTogglingStatus] = useState(false);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [deletingUser, setDeletingUser] = useState(false);

  // Get current user id from localStorage
  let currentUserId: number | null = null;
  try {
    const user = JSON.parse(localStorage.getItem("user") || "null");
    currentUserId = user?.id ?? null;
  } catch {
    currentUserId = null;
  }

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await api.get("/auth/users");
      console.log("Fetched users from API:", res);
      // The API returns the array directly, not wrapped in a data property
      setUsers(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.error("Failed to load users:", e);
      toast.error(getErrorMessage(e, t));
      setUsers([]); // Set empty array on error
    } finally {
      setLoading(false);
    }
  };

  const fetchInvites = async () => {
    try {
      const res = await api.get("/auth/invites");
      // The API returns the array directly, not wrapped in a data property
      setInvites(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.error("Failed to load invites:", e);
      toast.error(getErrorMessage(e, t));
      setInvites([]); // Set empty array on error
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchInvites();
  }, []);

  // Refetch data when tenant changes
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'selected_tenant_id') {
        fetchUsers();
        fetchInvites();
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  const handleInviteChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setInviteForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    try {
      await api.post("/auth/invite", inviteForm);
      toast.success(t('users.inviteSent'));
      setInviteForm({ email: "", first_name: "", last_name: "", role: "user" });
      setInviteDialogOpen(false);
      fetchInvites();
    } catch (err: any) {
      console.error("Failed to send invite:", err);
      toast.error(getErrorMessage(err, t));
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      console.log("Updating role for user", userId, "to", newRole);
      await api.put(`/auth/users/${userId}/role`, { role: newRole });
      console.log("Role update successful");
      toast.success(t('users.roleUpdated'));
      fetchUsers();
    } catch (err: any) {
      console.error("Failed to update role:", err);
      toast.error(getErrorMessage(err, t));
    }
  };

  const getInviteStatus = (invite: Invite) => {
    if (invite.is_accepted) return t('users.accepted');
    const now = new Date();
    const expiresAt = new Date(invite.expires_at);
    if (expiresAt < now) return t('users.expired');
    return t('users.pending');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case t('users.accepted'): return "text-green-600";
      case t('users.expired'): return "text-red-600";
      case t('users.pending'): return "text-yellow-600";
      default: return "text-gray-600";
    }
  };

  const openActivationDialog = (invite: Invite) => {
    setActivationInvite(invite);
    setActivationForm({
      password: "",
      first_name: invite.first_name || "",
      last_name: invite.last_name || "",
    });
    setActivationDialogOpen(true);
  };

  const closeActivationDialog = () => {
    setActivationDialogOpen(false);
    setActivationInvite(null);
    setActivationForm({ password: "", first_name: "", last_name: "" });
  };

  const handleActivationFormChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setActivationForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleActivateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activationInvite) return;
    setActivating(true);
    try {
      await api.post(`/auth/invites/${activationInvite.id}/activate`, activationForm);
      toast.success(t('users.userActivated'));
      closeActivationDialog();
      fetchUsers();
      fetchInvites();
    } catch (err: any) {
      console.error("Failed to activate user:", err);
      toast.error(getErrorMessage(err, t));
    } finally {
      setActivating(false);
    }
  };

  const handleCancelInvite = async (inviteId: number, inviteEmail: string) => {
    if (!confirm(t('users.confirmCancelInvite', { email: inviteEmail }))) {
      return;
    }

    setCancelling(true);
    try {
      await api.delete(`/auth/invites/${inviteId}`);
      toast.success(t('users.inviteCancelled'));
      fetchInvites();
    } catch (err: any) {
      console.error("Failed to cancel invite:", err);
      toast.error(getErrorMessage(err, t));
    } finally {
      setCancelling(false);
    }
  };

  const handleToggleUserStatus = async (userId: number, userEmail: string, isCurrentlyActive: boolean) => {
    const action = isCurrentlyActive ? t('users.deactivate') : t('users.activate');
    if (!confirm(t('users.confirmToggleStatus', { email: userEmail, action: action.toLowerCase() }))) {
      return;
    }

    setTogglingStatus(true);
    try {
      await superAdminApi.toggleUserStatus(userId);
      toast.success(t('users.statusToggled'));
      fetchUsers();
    } catch (err: any) {
      console.error("Failed to toggle user status:", err);
      toast.error(getErrorMessage(err, t));
    } finally {
      setTogglingStatus(false);
    }
  };

  const handleResetPassword = async (userId: number, userEmail: string) => {
    const newPassword = prompt(t('users.enterNewPassword', { email: userEmail }));
    if (!newPassword || newPassword.length < 6) {
      if (newPassword !== null) {
        toast.error(t('users.passwordTooShort'));
      }
      return;
    }

    setResettingPassword(true);
    try {
      await superAdminApi.resetUserPassword(userId, newPassword, false);
      toast.success(t('users.passwordReset'));
    } catch (err: any) {
      console.error("Failed to reset password:", err);
      toast.error(getErrorMessage(err, t));
    } finally {
      setResettingPassword(false);
    }
  };

  const handleDeleteUser = async (userId: number, userEmail: string) => {
    if (!confirm(t('users.confirmDeleteUser', { email: userEmail }))) {
      return;
    }

    setDeletingUser(true);
    try {
      await userApi.deleteUser(userId);
      toast.success(t('users.userDeleted'));
      fetchUsers();
    } catch (err: any) {
      console.error("Failed to delete user:", err);
      toast.error(getErrorMessage(err, t));
    } finally {
      setDeletingUser(false);
    }
  };



  // Filter users by search query
  const filteredUsers = users.filter(user =>
    user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    [user.first_name, user.last_name].filter(Boolean).join(" ").toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Sort users by email (case-insensitive)
  const sortedUsers = [...filteredUsers].sort((a, b) =>
    a.email.localeCompare(b.email, undefined, { sensitivity: 'base' })
  );

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{t('users.organizationUsers')}</h1>
            <p className="text-muted-foreground">{t('users.manageOrganizationUsers')}</p>
          </div>
          <Dialog open={inviteDialogOpen} onOpenChange={setInviteDialogOpen}>
            <DialogTrigger asChild>
              <Button className="sm:self-end whitespace-nowrap">
                <Plus className="mr-2 h-4 w-4" /> {t('users.inviteUser')}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('users.inviteUser')}</DialogTitle>
              </DialogHeader>
              <form className="space-y-4" onSubmit={handleInvite}>
                <Input
                  name="email"
                  type="email"
                  placeholder={t('users.emailPlaceholder')}
                  value={inviteForm.email}
                  onChange={handleInviteChange}
                  required
                />
                <div className="flex gap-2">
                  <Input
                    name="first_name"
                    placeholder={t('users.firstNamePlaceholder')}
                    value={inviteForm.first_name}
                    onChange={handleInviteChange}
                  />
                  <Input
                    name="last_name"
                    placeholder={t('users.lastNamePlaceholder')}
                    value={inviteForm.last_name}
                    onChange={handleInviteChange}
                  />
                </div>
                <Select
                  value={inviteForm.role}
                  onValueChange={(role: string) => setInviteForm((prev) => ({ ...prev, role }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('users.rolePlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.map((role) => (
                      <SelectItem key={role} value={role}>
                        {role.charAt(0).toUpperCase() + role.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <DialogFooter>
                  <Button type="submit" disabled={inviting}>
                    {inviting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {t('users.invite')}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <CardTitle>{t('users.allInvites')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('users.email')}</TableHead>
                    <TableHead>{t('users.name')}</TableHead>
                    <TableHead>{t('users.role')}</TableHead>
                    <TableHead>{t('users.status')}</TableHead>
                    <TableHead>{t('users.invitedBy')}</TableHead>
                    <TableHead>{t('users.expires')}</TableHead>
                    <TableHead>{t('users.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('users.loadingInvites')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (!invites || invites.length === 0) ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        {t('users.noInvitesFound')}
                      </TableCell>
                    </TableRow>
                  ) : (
                    invites.map((invite) => {
                      const status = getInviteStatus(invite);
                      return (
                        <TableRow key={invite.id}>
                          <TableCell>{invite.email}</TableCell>
                          <TableCell>{[invite.first_name, invite.last_name].filter(Boolean).join(" ") || "-"}</TableCell>
                          <TableCell>{invite.role.charAt(0).toUpperCase() + invite.role.slice(1)}</TableCell>
                          <TableCell className={getStatusColor(status)}>{status}</TableCell>
                          <TableCell>{invite.invited_by || "-"}</TableCell>
                          <TableCell>{new Date(invite.expires_at).toLocaleString()}</TableCell>
                          <TableCell>
                            {status === t('users.pending') && (
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => openActivationDialog(invite)}
                                  size="sm"
                                  className="bg-green-600 hover:bg-green-700"
                                >
                                  {t('users.activate')}
                                </Button>
                                <Button
                                  onClick={() => handleCancelInvite(invite.id, invite.email)}
                                  size="sm"
                                  variant="destructive"
                                  disabled={cancelling}
                                >
                                  {cancelling ? <Loader2 className="h-4 w-4 animate-spin" /> : t('users.cancel')}
                                </Button>
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {/* Join Requests Section */}
        <div className="slide-in">
          <JoinRequestsTable showAsCard={true} onRequestProcessed={fetchUsers} />
        </div>

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>{t('users.currentUsers')}</CardTitle>
              <div className="relative max-w-sm">
                <Input
                  placeholder={t('users.searchUsersPlaceholder')}
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('users.email')}</TableHead>
                    <TableHead>{t('users.name')}</TableHead>
                    <TableHead>{t('users.role')}</TableHead>
                    <TableHead>{t('users.status')}</TableHead>
                    <TableHead>{t('users.created')}</TableHead>
                    <TableHead>{t('users.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('users.loadingUsers')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (!filteredUsers || filteredUsers.length === 0) ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        {t('users.noUsersFound')}
                      </TableCell>
                    </TableRow>
                  ) : (
                    sortedUsers.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{[user.first_name, user.last_name].filter(Boolean).join(" ") || "-"}</TableCell>
                        <TableCell>{user.role.charAt(0).toUpperCase() + user.role.slice(1)}</TableCell>
                        <TableCell>{user.is_active ? t('users.active') : t('users.inactive')}</TableCell>
                        <TableCell>{new Date(user.created_at).toLocaleString()}</TableCell>
                        <TableCell>
                          <div className="flex gap-1 flex-wrap">
                            <Select
                              value={user.role}
                              onValueChange={(role: string) => handleRoleChange(user.id, role)}
                              disabled={user.id === currentUserId}
                            >
                              <SelectTrigger className="w-24 h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {ROLES.map((role) => (
                                  <SelectItem key={role} value={role}>
                                    {role.charAt(0).toUpperCase() + role.slice(1)}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>

                            <Button
                              size="sm"
                              variant={user.is_active ? "destructive" : "default"}
                              onClick={() => handleToggleUserStatus(user.id, user.email, user.is_active)}
                              disabled={togglingStatus || user.id === currentUserId}
                              className="h-8 px-2 text-xs"
                              title={user.is_active ? t('users.deactivateUser') : t('users.activateUser')}
                            >
                              {togglingStatus ? <Loader2 className="h-3 w-3 animate-spin" /> : (user.is_active ? t('users.deactivate') : t('users.activate'))}
                            </Button>

                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleResetPassword(user.id, user.email)}
                              disabled={resettingPassword}
                              className="h-8 px-2 text-xs"
                              title={t('users.resetPassword')}
                            >
                              {resettingPassword ? <Loader2 className="h-3 w-3 animate-spin" /> : t('users.reset')}
                            </Button>

                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteUser(user.id, user.email)}
                              disabled={deletingUser || user.id === currentUserId}
                              className="h-8 px-2 text-xs"
                              title={t('users.deleteUser')}
                            >
                              {deletingUser ? <Loader2 className="h-3 w-3 animate-spin" /> : t('users.delete')}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Dialog open={activationDialogOpen} onOpenChange={setActivationDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{t('users.activateUser')}: {activationInvite?.email}</DialogTitle>
              <p className="text-sm text-muted-foreground">
                {t('users.activationDescription') || 'Activate this user account. You can set their password now or send them an invitation to set it themselves.'}
              </p>
            </DialogHeader>
            <form onSubmit={handleActivateUser} className="space-y-4">
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Input
                    type="text"
                    name="first_name"
                    value={activationForm.first_name}
                    onChange={handleActivationFormChange}
                    placeholder={t('users.firstNamePlaceholder')}
                    className="flex-1"
                  />
                  <Input
                    type="text"
                    name="last_name"
                    value={activationForm.last_name}
                    onChange={handleActivationFormChange}
                    placeholder={t('users.lastNamePlaceholder')}
                    className="flex-1"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('users.passwordOptionLabel') || 'Password Setup'}
                  </label>
                  <Input
                    type="password"
                    name="password"
                    value={activationForm.password}
                    onChange={handleActivationFormChange}
                    placeholder={t('users.enterPasswordForUserPlaceholder')}
                  />
                  {activationForm.password && (
                    <div className="text-xs text-muted-foreground">
                      {t('users.passwordWillBeSet') || '✓ User will be able to login immediately with this password'}
                    </div>
                  )}
                  {!activationForm.password && (
                    <div className="text-xs text-amber-600">
                      {t('users.inviteWillBeSent') || '⚠ Leave blank to send invite email - user must set password on first login'}
                    </div>
                  )}
                  {activationForm.password && activationForm.password.length > 0 && activationForm.password.length < 6 && (
                    <div className="text-xs text-red-600">
                      {t('users.passwordTooShort') || 'Password must be at least 6 characters long'}
                    </div>
                  )}
                </div>
              </div>

              <DialogFooter className="flex gap-2">
                <Button type="button" variant="outline" onClick={closeActivationDialog} disabled={activating}>
                  {t('common.cancel')}
                </Button>
                <Button
                  type="submit"
                  disabled={activating || (activationForm.password && activationForm.password.length > 0 && activationForm.password.length < 6)}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {activating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  {activationForm.password ? (t('users.activateWithPassword') || 'Activate & Set Password') : (t('users.sendInvite') || 'Send Invite Email')}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>


      </div>
    </AppLayout>
  );
} 