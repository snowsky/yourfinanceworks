import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, ArrowRightLeft, Info, Shield, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { usePlugins } from "@/contexts/PluginContext";
import {
  PluginAccessGrantRecord,
  PluginAccessRequestRecord,
  PluginAccessType,
  pluginAccessApi,
} from "@/lib/plugin-access";

interface PluginAccessModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isAdmin: boolean;
}

export const PluginAccessModal: React.FC<PluginAccessModalProps> = ({
  open,
  onOpenChange,
  isAdmin,
}) => {
  const { t } = useTranslation();
  const { plugins } = usePlugins();

  const [accessSourcePlugin, setAccessSourcePlugin] = useState("");
  const [accessTargetPlugin, setAccessTargetPlugin] = useState("");
  const [accessType, setAccessType] = useState<PluginAccessType>("read");
  const [accessAllowedPaths, setAccessAllowedPaths] = useState("*");
  const [isUpdatingAccess, setIsUpdatingAccess] = useState(false);
  const [isLoadingAccessData, setIsLoadingAccessData] = useState(false);
  const [pendingAccessRequests, setPendingAccessRequests] = useState<
    PluginAccessRequestRecord[]
  >([]);
  const [accessGrants, setAccessGrants] = useState<PluginAccessGrantRecord[]>(
    [],
  );

  const enabledPluginIds = useMemo(
    () => plugins.filter((plugin) => plugin.enabled).map((plugin) => plugin.id),
    [plugins],
  );

  const getPluginDisplayName = (pluginId: string) => {
    return plugins.find((plugin) => plugin.id === pluginId)?.name || pluginId;
  };

  const loadPluginAccessData = useCallback(async () => {
    setIsLoadingAccessData(true);
    try {
      const [pendingResponse, grantsResponse] = await Promise.all([
        pluginAccessApi.listPendingMine(),
        pluginAccessApi.listGrantsMine(),
      ]);
      setPendingAccessRequests(pendingResponse.requests || []);
      setAccessGrants(grantsResponse.grants || []);
    } catch (error) {
      console.error("Failed to load cross-plugin access data:", error);
      toast.error(t("plugins.failed_load_access_settings"));
    } finally {
      setIsLoadingAccessData(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadPluginAccessData();
    }
  }, [open, loadPluginAccessData]);

  useEffect(() => {
    const handleAccessResolution = () => {
      if (open) {
        loadPluginAccessData();
      }
    };

    window.addEventListener(
      "plugin-access-approval-resolved",
      handleAccessResolution,
    );
    return () => {
      window.removeEventListener(
        "plugin-access-approval-resolved",
        handleAccessResolution,
      );
    };
  }, [open, loadPluginAccessData]);

  useEffect(() => {
    if (enabledPluginIds.length === 0) {
      setAccessSourcePlugin("");
      setAccessTargetPlugin("");
      return;
    }

    const nextSource = enabledPluginIds.includes(accessSourcePlugin)
      ? accessSourcePlugin
      : enabledPluginIds[0];
    if (nextSource !== accessSourcePlugin) {
      setAccessSourcePlugin(nextSource);
    }

    const targetOptions = enabledPluginIds.filter(
      (pluginId) => pluginId !== nextSource,
    );
    if (targetOptions.length === 0) {
      setAccessTargetPlugin("");
      return;
    }

    if (!targetOptions.includes(accessTargetPlugin)) {
      setAccessTargetPlugin(targetOptions[0]);
    }
  }, [enabledPluginIds, accessSourcePlugin, accessTargetPlugin]);

  const handleAllowCrossPluginAccess = async () => {
    if (!accessSourcePlugin || !accessTargetPlugin) {
      toast.error(t("plugins.choose_both_plugins_error"));
      return;
    }

    if (accessSourcePlugin === accessTargetPlugin) {
      toast.error(t("plugins.different_plugins_error_message"));
      return;
    }

    setIsUpdatingAccess(true);
    try {
      const checkResponse = await pluginAccessApi.check({
        source_plugin: accessSourcePlugin,
        target_plugin: accessTargetPlugin,
        access_type: accessType,
        reason: "Manual approval from Plugin Management",
        requested_path: accessAllowedPaths,
      });

      if (checkResponse.granted) {
        toast.success(
          t("plugins.already_has_access_message", {
            source: getPluginDisplayName(accessSourcePlugin),
            type: accessType,
            target: getPluginDisplayName(accessTargetPlugin),
          }),
        );
      } else if (checkResponse.request?.id) {
        await pluginAccessApi.approve(checkResponse.request.id);
        toast.success(
          t("plugins.allowed_access_success_message", {
            source: getPluginDisplayName(accessSourcePlugin),
            type: accessType,
            target: getPluginDisplayName(accessTargetPlugin),
          }),
        );
      } else {
        toast.error(t("plugins.plugin_initialization_failed_message", { error: "Unknown" }));
      }

      await loadPluginAccessData();
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Failed to allow plugin access";
      toast.error(errorMessage);
    } finally {
      setIsUpdatingAccess(false);
    }
  };

  const handleResolveAccessRequest = async (
    requestId: string,
    action: "approve" | "deny",
  ) => {
    setIsUpdatingAccess(true);
    try {
      if (action === "approve") {
        await pluginAccessApi.approve(requestId);
        toast.success(t("plugins.access_request_approved_success"));
      } else {
        await pluginAccessApi.deny(requestId);
        toast.success(t("plugins.access_request_denied_success"));
      }

      await loadPluginAccessData();
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : `Failed to ${action} access request`;
      toast.error(errorMessage);
    } finally {
      setIsUpdatingAccess(false);
    }
  };

  const handleRevokeAccessGrant = async (grantId: string) => {
    if (!window.confirm(t("plugins.revoke_confirm_message"))) {
      return;
    }

    setIsUpdatingAccess(true);
    try {
      await pluginAccessApi.revoke(grantId);
      toast.success(t("plugins.access_grant_revoked_success"));
      await loadPluginAccessData();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : t("plugins.failed_revoke_access_grant");
      toast.error(errorMessage);
    } finally {
      setIsUpdatingAccess(false);
    }
  };

  const targetPluginOptions = enabledPluginIds.filter(
    (pluginId) => pluginId !== accessSourcePlugin,
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-primary" />
            {t("plugins.plugin_access_title")}
          </DialogTitle>
          <DialogDescription>
            {t("plugins.plugin_access_description")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="text-xs text-muted-foreground">
            Need help?{" "}
            <a
              href="/docs/user-guide/PLUGIN_DATA_ACCESS_APPROVALS_USER_GUIDE.md"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:text-foreground"
            >
              {t("plugins.read_user_guide_link")}
            </a>
          </div>

          {!isAdmin && (
            <Alert variant="destructive">
              <Shield className="h-4 w-4" />
              <AlertDescription>
                <strong>{t("plugins.administrator_access_required")}:</strong>{" "}
                {t("plugins.plugin_management_restricted")}
              </AlertDescription>
            </Alert>
          )}

          {enabledPluginIds.length < 2 ? (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t("plugins.enable_two_plugins_warning_message")}
              </AlertDescription>
            </Alert>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end p-4 bg-muted/30 rounded-lg border">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {t("plugins.source_plugin_label")}
                </label>
                <select
                  value={accessSourcePlugin}
                  onChange={(event) =>
                    setAccessSourcePlugin(event.target.value)
                  }
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  disabled={!isAdmin}
                >
                  {enabledPluginIds.map((pluginId) => (
                    <option key={pluginId} value={pluginId}>
                      {getPluginDisplayName(pluginId)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {t("plugins.target_plugin_label")}
                </label>
                <select
                  value={accessTargetPlugin}
                  onChange={(event) =>
                    setAccessTargetPlugin(event.target.value)
                  }
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  disabled={!isAdmin}
                >
                  {targetPluginOptions.map((pluginId) => (
                    <option key={pluginId} value={pluginId}>
                      {getPluginDisplayName(pluginId)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {t("plugins.access_type_label")}
                </label>
                <select
                  value={accessType}
                  onChange={(event) =>
                    setAccessType(event.target.value as PluginAccessType)
                  }
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  disabled={!isAdmin}
                >
                  <option value="read">{t("plugins.read_access")}</option>
                  <option value="write">{t("plugins.write_access")}</option>
                </select>
              </div>

                <Button
                  type="button"
                  onClick={handleAllowCrossPluginAccess}
                  disabled={
                    isUpdatingAccess ||
                    !accessSourcePlugin ||
                    !accessTargetPlugin ||
                    !isAdmin
                  }
                >
                  {isUpdatingAccess ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : null}
                  {t("plugins.allow_access_button")}
                </Button>
              </div>

              <div className="grid grid-cols-1 p-4 pt-0 bg-muted/30 rounded-lg border-x border-b -mt-1">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    {t("plugins.allowed_paths_label")}
                  </label>
                  <input
                    type="text"
                    value={accessAllowedPaths}
                    onChange={(e) => setAccessAllowedPaths(e.target.value)}
                    placeholder="e.g. /api/v1/investments/stats*, /api/v1/investments/summary"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    disabled={!isAdmin}
                  />
                </div>
              </div>
            </>
          )}

          <div className="space-y-3">
            <h4 className="text-sm font-semibold flex items-center gap-2">
              {t("plugins.pending_requests")}
              {pendingAccessRequests.length > 0 && (
                <Badge
                  variant="outline"
                  className="text-[10px] h-5 px-1.5 bg-amber-50"
                >
                  {pendingAccessRequests.length}
                </Badge>
              )}
            </h4>
            {isLoadingAccessData ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                {t("plugins.loading_requests_message")}
              </div>
            ) : pendingAccessRequests.length === 0 ? (
              <div className="text-sm text-muted-foreground border border-dashed rounded-lg p-6 text-center">
                {t("plugins.no_pending_requests_message")}
              </div>
            ) : (
              <div className="space-y-2">
                {pendingAccessRequests.map((request) => (
                  <div
                    key={request.id}
                    className="flex flex-col md:flex-row md:items-center justify-between gap-3 rounded-md border p-3 bg-background shadow-sm"
                  >
                    <div className="text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-primary">
                          {getPluginDisplayName(request.source_plugin)}
                        </span>
                        <ArrowRightLeft className="w-3 h-3 text-muted-foreground" />
                        <span className="font-semibold text-primary">
                          {getPluginDisplayName(request.target_plugin)}
                        </span>
                      </div>
                      <Badge
                        variant="outline"
                        className="mt-1 text-[10px] uppercase font-bold tracking-tight px-1 h-4"
                      >
                        {request.access_type}
                      </Badge>
                      {request.requested_path && (
                        <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded w-fit">
                          <code className="text-primary/70">{request.requested_path}</code>
                        </div>
                      )}
                      {request.reason ? (
                        <div className="text-xs text-muted-foreground mt-2 italic border-l-2 pl-2 border-primary/20">
                          "{request.reason}"
                        </div>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2 mt-2 md:mt-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() =>
                          handleResolveAccessRequest(request.id, "deny")
                        }
                        disabled={isUpdatingAccess || !isAdmin}
                      >
                        {t("plugins.deny_button")}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() =>
                          handleResolveAccessRequest(request.id, "approve")
                        }
                        disabled={isUpdatingAccess || !isAdmin}
                      >
                        {t("plugins.approve_button")}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <h4 className="text-sm font-semibold">{t("plugins.active_grants")}</h4>
            {isLoadingAccessData ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                {t("plugins.loading_grants_message")}
              </div>
            ) : accessGrants.length === 0 ? (
              <div className="text-sm text-muted-foreground border border-dashed rounded-lg p-6 text-center">
                {t("plugins.no_active_grants_message")}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {accessGrants.map((grant) => (
                  <div
                    key={grant.id}
                    className="flex items-center gap-2 p-2 border rounded-md bg-muted/50 text-xs text-foreground/80"
                  >
                    <Shield className="w-3 h-3 text-green-600" />
                    <span className="truncate flex-1">
                      <span className="font-medium">
                        {getPluginDisplayName(grant.source_plugin)}
                      </span>
                      {" → "}
                      <span className="font-medium">
                        {getPluginDisplayName(grant.target_plugin)}
                      </span>
                    </span>
                    <Badge
                      variant="outline"
                      className="text-[9px] h-4 px-1 lowercase scale-90"
                    >
                      {grant.access_type}
                    </Badge>
                    {grant.allowed_paths && (
                      <div className="text-[9px] text-muted-foreground border-l pl-2 max-w-[150px] truncate" title={grant.allowed_paths.join(', ')}>
                        {grant.allowed_paths.join(', ')}
                      </div>
                    )}
                    {isAdmin && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 ml-auto text-muted-foreground hover:text-red-600 hover:bg-red-50"
                        onClick={() => handleRevokeAccessGrant(grant.id)}
                        title={t("plugins.revoke_access_title")}
                        disabled={isUpdatingAccess}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.close")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
