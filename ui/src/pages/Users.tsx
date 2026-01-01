import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, superAdminApi, userApi } from "@/lib/api";
import { toast } from "@/components/ui/sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import { Loader2, Plus, Search, Mail, CheckCircle2 } from "lucide-react";
import { useTranslation } from 'react-i18next';
import { getErrorMessage } from '@/lib/api';
import { JoinRequestsTable } from '@/components/JoinRequestsTable';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard, ProfessionalCardHeader, ProfessionalCardTitle, ProfessionalCardContent, ProfessionalCardDescription } from '@/components/ui/professional-card';
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalInput } from "@/components/ui/professional-input";
import {
  ProfessionalTable,
  ProfessionalTableHeader,
  ProfessionalTableBody,
  ProfessionalTableHead,
  ProfessionalTableRow,
  ProfessionalTableCell,
  StatusBadge,
  TableActionMenu
} from "@/components/ui/professional-table";
import { getCurrentUser } from '@/utils/auth';
import { useOrganizations } from '@/hooks/useOrganizations';

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
  const navigate = useNavigate();
  const user = getCurrentUser();
  const { data: userOrganizations = [] } = useOrganizations();

  const [users, setUsers] = useState<User[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasAccess, setHasAccess] = useState(false);
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

  // Check permission to access users page
  useEffect(() => {
    // Get current organization ID from localStorage
    const currentOrgId = localStorage.getItem('selected_tenant_id') || user?.tenant_id?.toString() || '';
    const currentOrg = userOrganizations.find(org => org.id.toString() === currentOrgId);
    const isAdminInCurrentOrg = currentOrg?.role === 'admin';
    setHasAccess(isAdminInCurrentOrg);

    if (userOrganizations.length > 0 && !isAdminInCurrentOrg) {
      navigate('/');
    }
  }, [userOrganizations, navigate, user?.tenant_id]);

  // User management states
  const [togglingStatus, setTogglingStatus] = useState(false);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [deletingUser, setDeletingUser] = useState(false);
  const [resetPasswordModalOpen, setResetPasswordModalOpen] = useState(false);
  const [userToReset, setUserToReset] = useState<User | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

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
      setUsers(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.error("Failed to load users:", e);
      toast.error(getErrorMessage(e, t));
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchInvites = async () => {
    try {
      const res = await api.get("/auth/invites");
      setInvites(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.error("Failed to load invites:", e);
      toast.error(getErrorMessage(e, t));
      setInvites([]);
    }
  };

  useEffect(() => {
    if (hasAccess) {
      fetchUsers();
      fetchInvites();
    }
  }, [hasAccess]);

  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'selected_tenant_id' && hasAccess) {
        fetchUsers();
        fetchInvites();
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [hasAccess]);

  const handleInviteChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setInviteForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    try {
      await api.post("/auth/invite", inviteForm);
      toast.success(t('users.invite_user'));
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
      await api.put(`/auth/users/${userId}/role`, { role: newRole });
      toast.success(t('users.role_updated'));
      fetchUsers();
    } catch (err: any) {
      console.error("Failed to update role:", err);
      toast.error(getErrorMessage(err, t));
    }
  };

  const getInviteStatus = (invite: Invite) => {
    if (invite.is_accepted) return 'accepted';
    const now = new Date();
    const expiresAt = new Date(invite.expires_at);
    if (expiresAt < now) return 'expired';
    return 'pending';
  };

  const getInviteStatusBadge = (status: string) => {
    switch (status) {
      case 'accepted':
        return <StatusBadge status="success">{t('users.accepted')}</StatusBadge>;
      case 'expired':
        return <StatusBadge status="danger">{t('users.expired')}</StatusBadge>;
      case 'pending':
        return <StatusBadge status="warning">{t('users.pending')}</StatusBadge>;
      default:
        return <StatusBadge status="neutral">{status}</StatusBadge>;
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
      toast.success(t('users.user_activated'));
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

  const openResetPasswordModal = (user: User) => {
    setUserToReset(user);
    setNewPassword("");
    setConfirmPassword("");
    setResetPasswordModalOpen(true);
  };

  const closeResetPasswordModal = () => {
    setResetPasswordModalOpen(false);
    setUserToReset(null);
    setNewPassword("");
    setConfirmPassword("");
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userToReset) return;

    if (newPassword.length < 6) {
      toast.error(t('users.passwordTooShort'));
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error(t('users.passwordsDoNotMatch'));
      return;
    }

    setResettingPassword(true);
    try {
      await superAdminApi.resetUserPassword(userToReset.id, newPassword, false);
      toast.success(t('users.passwordReset'));
      closeResetPasswordModal();
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

  const filteredUsers = users.filter(user =>
    user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    [user.first_name, user.last_name].filter(Boolean).join(" ").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const sortedUsers = [...filteredUsers].sort((a, b) =>
    a.email.localeCompare(b.email, undefined, { sensitivity: 'base' })
  );

  return (
    <div className="h-full space-y-8 p-8 fade-in">
      <PageHeader
        title={t('users.organization_users')}
        description={t('users.manageorganization_users')}
        actions={
          <Dialog open={inviteDialogOpen} onOpenChange={setInviteDialogOpen}>
            <DialogTrigger asChild>
              <ProfessionalButton className="sm:self-end whitespace-nowrap" variant="gradient">
                <Plus className="mr-2 h-4 w-4" /> {t('users.invite_user')}
              </ProfessionalButton>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('users.invite_user')}</DialogTitle>
              </DialogHeader>
              <form className="space-y-4" onSubmit={handleInvite}>
                <ProfessionalInput
                  name="email"
                  type="email"
                  placeholder={t('users.email_placeholder')}
                  value={inviteForm.email}
                  onChange={handleInviteChange}
                  required
                  leftIcon={<Mail className="h-4 w-4" />}
                />
                <div className="flex gap-2">
                  <ProfessionalInput
                    name="first_name"
                    placeholder={t('users.first_name_placeholder')}
                    value={inviteForm.first_name}
                    onChange={handleInviteChange}
                  />
                  <ProfessionalInput
                    name="last_name"
                    placeholder={t('users.last_name_placeholder')}
                    value={inviteForm.last_name}
                    onChange={handleInviteChange}
                  />
                </div>
                <Select
                  value={inviteForm.role}
                  onValueChange={(role: string) => setInviteForm((prev) => ({ ...prev, role }))}
                >
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder={t('users.role_placeholder')} />
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
                  <ProfessionalButton type="submit" disabled={inviting} loading={inviting} variant="gradient">
                    {t('users.invite')}
                  </ProfessionalButton>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {invites && invites.length > 0 && (
        <ProfessionalCard className="slide-in" variant="elevated">
          <ProfessionalCardHeader>
            <ProfessionalCardTitle>{t('users.all_invites')}</ProfessionalCardTitle>
            <ProfessionalCardDescription>{t('users.all_invites_desc', 'Pending and past invitations')}</ProfessionalCardDescription>
          </ProfessionalCardHeader>
          <ProfessionalCardContent>
            <ProfessionalTable>
              <ProfessionalTableHeader>
                <ProfessionalTableRow>
                  <ProfessionalTableHead>{t('users.email')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('users.name')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('users.role')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('users.status')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('users.invited_by')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('users.expires')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('users.actions')}</ProfessionalTableHead>
                </ProfessionalTableRow>
              </ProfessionalTableHeader>
              <ProfessionalTableBody>
                {loading ? (
                  <ProfessionalTableRow>
                    <ProfessionalTableCell colSpan={7} className="h-24 text-center">
                      <div className="flex justify-center items-center">
                        <Loader2 className="h-6 w-6 animate-spin mr-2" />
                        {t('users.loadingInvites')}
                      </div>
                    </ProfessionalTableCell>
                  </ProfessionalTableRow>
                ) : (
                  invites.map((invite) => {
                    const status = getInviteStatus(invite);
                    return (
                      <ProfessionalTableRow key={invite.id}>
                        <ProfessionalTableCell className="font-medium">{invite.email}</ProfessionalTableCell>
                        <ProfessionalTableCell>{[invite.first_name, invite.last_name].filter(Boolean).join(" ") || "-"}</ProfessionalTableCell>
                        <ProfessionalTableCell>
                          <StatusBadge status="neutral" variant="outline">
                            {invite.role.charAt(0).toUpperCase() + invite.role.slice(1)}
                          </StatusBadge>
                        </ProfessionalTableCell>
                        <ProfessionalTableCell>{getInviteStatusBadge(status)}</ProfessionalTableCell>
                        <ProfessionalTableCell>{invite.invited_by || "-"}</ProfessionalTableCell>
                        <ProfessionalTableCell className="text-muted-foreground">{new Date(invite.expires_at).toLocaleDateString()}</ProfessionalTableCell>
                        <ProfessionalTableCell>
                          {status === 'pending' && (
                            <div className="flex gap-2">
                              <ProfessionalButton
                                onClick={() => openActivationDialog(invite)}
                                size="sm"
                                variant="outline"
                                className="h-8 border-green-500/20 text-green-600 hover:bg-green-500/10 hover:text-green-700 hover:border-green-500/30"
                              >
                                {t('users.activate')}
                              </ProfessionalButton>
                              <ProfessionalButton
                                onClick={() => handleCancelInvite(invite.id, invite.email)}
                                size="sm"
                                variant="destructive"
                                disabled={cancelling}
                                className="h-8"
                              >
                                {cancelling ? <Loader2 className="h-4 w-4 animate-spin" /> : t('users.cancel')}
                              </ProfessionalButton>
                            </div>
                          )}
                        </ProfessionalTableCell>
                      </ProfessionalTableRow>
                    );
                  })
                )}
              </ProfessionalTableBody>
            </ProfessionalTable>
          </ProfessionalCardContent>
        </ProfessionalCard>
      )}

      {/* Join Requests Section */}
      <div className="slide-in">
        <JoinRequestsTable showAsCard={true} onRequestProcessed={fetchUsers} />
      </div>

      <ProfessionalCard className="slide-in" variant="elevated">
        <ProfessionalCardHeader>
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <ProfessionalCardTitle>{t('users.team_members', 'Team Members')}</ProfessionalCardTitle>
              <ProfessionalCardDescription>{t('users.manage_access_and_roles', 'Manage access and roles for your team.')}</ProfessionalCardDescription>
            </div>
            <div className="relative w-full sm:w-[300px]">
              <ProfessionalInput
                placeholder={t('users.search_users_placeholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                leftIcon={<Search className="h-4 w-4 text-muted-foreground" />}
              />
            </div>
          </div>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <ProfessionalTable>
            <ProfessionalTableHeader>
              <ProfessionalTableRow>
                <ProfessionalTableHead>{t('users.email')}</ProfessionalTableHead>
                <ProfessionalTableHead>{t('users.name')}</ProfessionalTableHead>
                <ProfessionalTableHead>{t('users.role')}</ProfessionalTableHead>
                <ProfessionalTableHead>{t('users.status')}</ProfessionalTableHead>
                <ProfessionalTableHead>{t('users.created')}</ProfessionalTableHead>
                <ProfessionalTableHead className="text-right">{t('users.actions')}</ProfessionalTableHead>
              </ProfessionalTableRow>
            </ProfessionalTableHeader>
            <ProfessionalTableBody>
              {loading ? (
                <ProfessionalTableRow>
                  <ProfessionalTableCell colSpan={6} className="h-24 text-center">
                    <div className="flex justify-center items-center">
                      <Loader2 className="h-6 w-6 animate-spin mr-2" />
                      {t('users.loading_users')}
                    </div>
                  </ProfessionalTableCell>
                </ProfessionalTableRow>
              ) : (!filteredUsers || filteredUsers.length === 0) ? (
                <ProfessionalTableRow>
                  <ProfessionalTableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                    {t('users.no_users_found')}
                  </ProfessionalTableCell>
                </ProfessionalTableRow>
              ) : (
                sortedUsers.map((user) => (
                  <ProfessionalTableRow key={user.id}>
                    <ProfessionalTableCell className="font-medium">{user.email}</ProfessionalTableCell>
                    <ProfessionalTableCell>{[user.first_name, user.last_name].filter(Boolean).join(" ") || "-"}</ProfessionalTableCell>
                    <ProfessionalTableCell>
                      {user.id === currentUserId ? (
                        <StatusBadge status="neutral" variant="outline">{user.role.charAt(0).toUpperCase() + user.role.slice(1)}</StatusBadge>
                      ) : (
                        <Select
                          value={user.role}
                          onValueChange={(role: string) => handleRoleChange(user.id, role)}
                        >
                          <SelectTrigger className="w-28 h-8 text-xs border-border/50 bg-background/50">
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
                      )}
                    </ProfessionalTableCell>
                    <ProfessionalTableCell>
                      <StatusBadge status={user.is_active ? "success" : "neutral"}>
                        {user.is_active ? t('users.active') : t('users.inactive')}
                      </StatusBadge>
                    </ProfessionalTableCell>
                    <ProfessionalTableCell className="text-muted-foreground">{new Date(user.created_at).toLocaleDateString()}</ProfessionalTableCell>
                    <ProfessionalTableCell className="text-right">
                      <TableActionMenu
                        actions={[
                          {
                            label: user.is_active ? t('users.deactivate') : t('users.activate'),
                            onClick: () => handleToggleUserStatus(user.id, user.email, user.is_active),
                            disabled: togglingStatus || user.id === currentUserId,
                            variant: user.is_active ? 'destructive' : 'default'
                          },
                          {
                            label: t('users.resetPassword'),
                            onClick: () => openResetPasswordModal(user),
                            disabled: resettingPassword
                          },
                          {
                            label: t('users.delete'),
                            onClick: () => handleDeleteUser(user.id, user.email),
                            disabled: deletingUser || user.id === currentUserId,
                            variant: 'destructive'
                          }
                        ]}
                      />
                    </ProfessionalTableCell>
                  </ProfessionalTableRow>
                ))
              )}
            </ProfessionalTableBody>
          </ProfessionalTable>
        </ProfessionalCardContent>
      </ProfessionalCard>

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
                <ProfessionalInput
                  type="text"
                  name="first_name"
                  value={activationForm.first_name}
                  onChange={handleActivationFormChange}
                  placeholder={t('users.first_name_placeholder')}
                  className="flex-1"
                />
                <ProfessionalInput
                  type="text"
                  name="last_name"
                  value={activationForm.last_name}
                  onChange={handleActivationFormChange}
                  placeholder={t('users.last_name_placeholder')}
                  className="flex-1"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t('users.passwordOptionLabel') || 'Password Setup'}
                </label>
                <ProfessionalInput
                  type="password"
                  name="password"
                  value={activationForm.password}
                  onChange={handleActivationFormChange}
                  placeholder={t('users.enterPasswordForUserPlaceholder')}
                />
                {activationForm.password && (
                  <div className="text-xs text-muted-foreground flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-green-600" />
                    {t('users.passwordWillBeSet') || 'User will be able to login immediately with this password'}
                  </div>
                )}
                {!activationForm.password && (
                  <div className="text-xs text-amber-600 flex items-center gap-1">
                    <Mail className="w-3 h-3" />
                    {t('users.inviteWillBeSent') || 'Leave blank to send invite email'}
                  </div>
                )}
                {activationForm.password && activationForm.password.length > 0 && activationForm.password.length < 6 && (
                  <div className="text-xs text-destructive">
                    {t('users.passwordTooShort') || 'Password must be at least 6 characters long'}
                  </div>
                )}
              </div>
            </div>

            <DialogFooter className="flex gap-2">
              <ProfessionalButton type="button" variant="outline" onClick={closeActivationDialog} disabled={activating}>
                {t('common.cancel')}
              </ProfessionalButton>
              <ProfessionalButton
                type="submit"
                variant="gradient"
                disabled={activating || (activationForm.password && activationForm.password.length > 0 && activationForm.password.length < 6)}
              >
                {activationForm.password ? (t('users.activateWithPassword') || 'Activate & Set Password') : (t('users.sendInvite') || 'Send Invite Email')}
              </ProfessionalButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={resetPasswordModalOpen} onOpenChange={setResetPasswordModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('users.resetPassword')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('users.resetPasswordDescription', { email: userToReset?.email })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <form onSubmit={handleResetPassword} className="space-y-4">
            <div className="space-y-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t('users.newPassword')}
                </label>
                <ProfessionalInput
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder={t('users.enterNewPassword')}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t('users.confirmPassword')}
                </label>
                <ProfessionalInput
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder={t('users.confirmNewPassword')}
                  required
                />
              </div>
              {newPassword && newPassword.length > 0 && newPassword.length < 6 && (
                <div className="text-xs text-destructive">
                  {t('users.passwordTooShort')}
                </div>
              )}
              {newPassword && confirmPassword && newPassword !== confirmPassword && (
                <div className="text-xs text-destructive">
                  {t('users.passwordsDoNotMatch')}
                </div>
              )}
            </div>
            <AlertDialogFooter className="flex gap-2">
              <AlertDialogCancel disabled={resettingPassword}>
                {t('common.cancel')}
              </AlertDialogCancel>
              <AlertDialogAction
                type="submit"
                disabled={resettingPassword || !newPassword || !confirmPassword || newPassword !== confirmPassword || newPassword.length < 6}
                className="bg-primary hover:bg-primary/90"
              >
                {resettingPassword ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {t('users.resetPassword')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </form>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  );
}