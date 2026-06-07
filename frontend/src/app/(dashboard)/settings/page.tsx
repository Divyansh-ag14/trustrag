"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Settings,
  Users,
  Key,
  Loader2,
  Plus,
  Trash2,
  Copy,
  Check,
  Shield,
  Eye,
  Pencil,
  Plug,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api-client";
import { ConnectorList } from "@/components/connectors/connector-list";
import { ConnectorDialog } from "@/components/connectors/connector-dialog";
import type { Connector, ConnectorCreate } from "@/types/api";

interface WorkspaceInfo {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
  created_at: string;
}

interface TeamUser {
  id: string;
  email: string;
  name: string;
  role: string;
  created_at: string;
}

interface ApiKeyInfo {
  id: string;
  name: string;
  key_prefix: string;
  key?: string;
  permissions: string[];
  last_used_at: string | null;
  created_at: string;
  expires_at: string | null;
}

const ROLE_COLORS: Record<string, string> = {
  admin: "border-red-500/30 text-red-400",
  member: "border-blue-500/30 text-blue-400",
  viewer: "border-zinc-500/30 text-zinc-400",
};

const ROLE_ICONS: Record<string, typeof Shield> = {
  admin: Shield,
  member: Pencil,
  viewer: Eye,
};

export default function SettingsPage() {
  const authUser = useAuthStore((s) => s.user);
  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Connectors
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [connectorsLoading, setConnectorsLoading] = useState(true);
  const [connectorDialogOpen, setConnectorDialogOpen] = useState(false);
  const [editingConnector, setEditingConnector] = useState<Connector | null>(null);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  // Dialogs
  const [inviteOpen, setInviteOpen] = useState(false);
  const [createKeyOpen, setCreateKeyOpen] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Form state
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [invitePassword, setInvitePassword] = useState("");
  const [keyName, setKeyName] = useState("");
  const [wsName, setWsName] = useState("");
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [ws, u, k] = await Promise.all([
        api.get<WorkspaceInfo>("/admin/workspace"),
        api.get<TeamUser[]>("/admin/users"),
        api.get<ApiKeyInfo[]>("/admin/api-keys"),
      ]);
      setWorkspace(ws);
      setWsName(ws.name);
      setUsers(u);
      setApiKeys(k);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchConnectors = useCallback(async () => {
    try {
      const data = await api.get<Connector[]>("/connectors");
      setConnectors(data);
    } catch {
      // silent
    } finally {
      setConnectorsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    fetchConnectors();
  }, [fetchAll, fetchConnectors]);

  const saveWorkspace = async () => {
    if (!wsName.trim()) return;
    setSaving(true);
    try {
      const updated = await api.patch<WorkspaceInfo>("/admin/workspace", {
        name: wsName,
      });
      setWorkspace(updated);
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const inviteUser = async () => {
    if (!inviteEmail || !inviteName || !invitePassword) return;
    try {
      await api.post("/admin/users/invite", {
        email: inviteEmail,
        name: inviteName,
        role: inviteRole,
        password: invitePassword,
      });
      setInviteOpen(false);
      setInviteName("");
      setInviteEmail("");
      setInviteRole("member");
      setInvitePassword("");
      fetchAll();
    } catch {
      // silent
    }
  };

  const removeUser = async (userId: string) => {
    try {
      await api.delete(`/admin/users/${userId}`);
      fetchAll();
    } catch {
      // silent
    }
  };

  const changeRole = async (userId: string, role: string) => {
    try {
      await api.patch(`/admin/users/${userId}/role`, { role });
      fetchAll();
    } catch {
      // silent
    }
  };

  const createApiKey = async () => {
    if (!keyName) return;
    try {
      const result = await api.post<ApiKeyInfo>("/admin/api-keys", {
        name: keyName,
        permissions: ["query"],
      });
      setNewKey(result.key || null);
      setKeyName("");
      fetchAll();
    } catch {
      // silent
    }
  };

  const revokeKey = async (keyId: string) => {
    try {
      await api.delete(`/admin/api-keys/${keyId}`);
      fetchAll();
    } catch {
      // silent
    }
  };

  const copyKey = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleCreateConnector = async (data: ConnectorCreate) => {
    await api.post("/connectors", data);
    fetchConnectors();
  };

  const handleEditConnector = async (data: ConnectorCreate) => {
    if (!editingConnector) return;
    await api.patch(`/connectors/${editingConnector.id}`, data);
    setEditingConnector(null);
    fetchConnectors();
  };

  const handleDeleteConnector = async (id: string) => {
    try {
      await api.delete(`/connectors/${id}`);
      fetchConnectors();
    } catch {
      // silent
    }
  };

  const handleSyncConnector = async (id: string) => {
    setSyncingIds((prev) => new Set(prev).add(id));
    try {
      await api.post(`/connectors/${id}/sync`);
    } catch {
      // silent
    } finally {
      setTimeout(() => {
        setSyncingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
        fetchConnectors();
      }, 3000);
    }
  };

  const handleTestConnector = async (
    data: ConnectorCreate,
  ): Promise<{ success: boolean; message: string }> => {
    try {
      const result = await api.post<{ success: boolean; message: string }>(
        "/connectors/test",
        data,
      );
      return { success: result.success, message: result.message };
    } catch {
      return { success: false, message: "Request failed — could not reach the server" };
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your workspace configuration
        </p>
      </div>

      <Tabs defaultValue="workspace">
        <TabsList>
          <TabsTrigger value="workspace" className="text-xs gap-1.5">
            <Settings className="h-3 w-3" />
            Workspace
          </TabsTrigger>
          <TabsTrigger value="users" className="text-xs gap-1.5">
            <Users className="h-3 w-3" />
            Users
          </TabsTrigger>
          <TabsTrigger value="connectors" className="text-xs gap-1.5">
            <Plug className="h-3 w-3" />
            Connectors
          </TabsTrigger>
          <TabsTrigger value="api-keys" className="text-xs gap-1.5">
            <Key className="h-3 w-3" />
            API Keys
          </TabsTrigger>
        </TabsList>

        {/* ── Workspace Tab ── */}
        <TabsContent value="workspace" className="mt-4 space-y-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader>
              <CardTitle className="text-sm">General</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Workspace name</label>
                <div className="flex gap-2">
                  <Input
                    value={wsName}
                    onChange={(e) => setWsName(e.target.value)}
                    placeholder="My Workspace"
                  />
                  <Button
                    size="sm"
                    onClick={saveWorkspace}
                    disabled={saving || wsName === workspace?.name}
                  >
                    {saving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Save"
                    )}
                  </Button>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Slug</label>
                <p className="text-sm text-muted-foreground">
                  {workspace?.slug}
                </p>
              </div>
              <Separator className="opacity-40" />
              <div className="space-y-2">
                <label className="text-sm font-medium">Your profile</label>
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    value={authUser?.name || ""}
                    disabled
                    placeholder="Name"
                  />
                  <Input
                    value={authUser?.email || ""}
                    disabled
                    placeholder="Email"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Created</label>
                <p className="text-sm text-muted-foreground">
                  {workspace?.created_at
                    ? new Date(workspace.created_at).toLocaleDateString()
                    : "--"}
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Users Tab ── */}
        <TabsContent value="users" className="mt-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">
                Team members ({users.length})
              </CardTitle>
              <Button
                size="sm"
                className="gap-1.5"
                onClick={() => setInviteOpen(true)}
              >
                <Plus className="h-3.5 w-3.5" />
                Add user
              </Button>
            </CardHeader>
            <CardContent>
              <div className="border border-border/40 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/40 bg-muted/30">
                      <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                        Name
                      </th>
                      <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                        Email
                      </th>
                      <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                        Role
                      </th>
                      <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                        Joined
                      </th>
                      <th className="text-right py-2.5 px-4 font-medium text-muted-foreground w-20">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr
                        key={u.id}
                        className="border-b border-border/20 last:border-0"
                      >
                        <td className="py-2.5 px-4 font-medium">{u.name}</td>
                        <td className="py-2.5 px-4 text-muted-foreground">
                          {u.email}
                        </td>
                        <td className="py-2.5 px-4">
                          <select
                            value={u.role}
                            onChange={(e) => changeRole(u.id, e.target.value)}
                            disabled={u.id === authUser?.id}
                            className="bg-transparent text-xs border border-border/40 rounded px-2 py-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <option value="admin">Admin</option>
                            <option value="member">Member</option>
                            <option value="viewer">Viewer</option>
                          </select>
                        </td>
                        <td className="py-2.5 px-4 text-muted-foreground text-xs">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          {u.id !== authUser?.id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
                              onClick={() => removeUser(u.id)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Connectors Tab ── */}
        <TabsContent value="connectors" className="mt-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">
                Data connectors ({connectors.length})
              </CardTitle>
              <Button
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  setEditingConnector(null);
                  setConnectorDialogOpen(true);
                }}
              >
                <Plus className="h-3.5 w-3.5" />
                Add connector
              </Button>
            </CardHeader>
            <CardContent>
              <ConnectorList
                connectors={connectors}
                loading={connectorsLoading}
                onSync={handleSyncConnector}
                onEdit={(conn) => {
                  setEditingConnector(conn);
                  setConnectorDialogOpen(true);
                }}
                onDelete={handleDeleteConnector}
                syncingIds={syncingIds}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── API Keys Tab ── */}
        <TabsContent value="api-keys" className="mt-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">API Keys</CardTitle>
              <Button
                size="sm"
                className="gap-1.5"
                onClick={() => setCreateKeyOpen(true)}
              >
                <Plus className="h-3.5 w-3.5" />
                Create key
              </Button>
            </CardHeader>
            <CardContent>
              {apiKeys.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Key className="h-8 w-8 text-muted-foreground/40 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No API keys yet
                  </p>
                  <p className="text-xs text-muted-foreground/60 mt-1">
                    Create an API key for programmatic access
                  </p>
                </div>
              ) : (
                <div className="border border-border/40 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/40 bg-muted/30">
                        <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                          Name
                        </th>
                        <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                          Key
                        </th>
                        <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                          Permissions
                        </th>
                        <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">
                          Created
                        </th>
                        <th className="text-right py-2.5 px-4 font-medium text-muted-foreground w-20">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {apiKeys.map((k) => (
                        <tr
                          key={k.id}
                          className="border-b border-border/20 last:border-0"
                        >
                          <td className="py-2.5 px-4 font-medium">{k.name}</td>
                          <td className="py-2.5 px-4">
                            <code className="text-xs bg-muted/30 px-2 py-0.5 rounded">
                              {k.key_prefix}...
                            </code>
                          </td>
                          <td className="py-2.5 px-4">
                            <div className="flex gap-1">
                              {k.permissions.map((p) => (
                                <Badge
                                  key={p}
                                  variant="outline"
                                  className="text-[10px]"
                                >
                                  {p}
                                </Badge>
                              ))}
                            </div>
                          </td>
                          <td className="py-2.5 px-4 text-muted-foreground text-xs">
                            {new Date(k.created_at).toLocaleDateString()}
                          </td>
                          <td className="py-2.5 px-4 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
                              onClick={() => revokeKey(k.id)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Invite User Dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add team member</DialogTitle>
            <DialogDescription>
              Add a new user to this workspace
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Input
              placeholder="Name"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
            />
            <Input
              type="email"
              placeholder="Email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <Input
              type="password"
              placeholder="Password"
              value={invitePassword}
              onChange={(e) => setInvitePassword(e.target.value)}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="w-full bg-transparent text-sm border border-border rounded-md px-3 py-2"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteOpen(false)}>
              Cancel
            </Button>
            <Button onClick={inviteUser}>Add user</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Connector Dialog */}
      <ConnectorDialog
        open={connectorDialogOpen}
        onOpenChange={(open) => {
          setConnectorDialogOpen(open);
          if (!open) setEditingConnector(null);
        }}
        onSubmit={editingConnector ? handleEditConnector : handleCreateConnector}
        onTest={!editingConnector ? handleTestConnector : undefined}
        editConnector={editingConnector}
      />

      {/* Create API Key Dialog */}
      <Dialog
        open={createKeyOpen}
        onOpenChange={(open) => {
          setCreateKeyOpen(open);
          if (!open) setNewKey(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {newKey ? "API key created" : "Create API key"}
            </DialogTitle>
            <DialogDescription>
              {newKey
                ? "Copy this key now. It won't be shown again."
                : "Create a key for programmatic API access"}
            </DialogDescription>
          </DialogHeader>
          {newKey ? (
            <div className="space-y-3 py-2">
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-muted/30 px-3 py-2 rounded-md break-all">
                  {newKey}
                </code>
                <Button variant="outline" size="sm" onClick={copyKey}>
                  {copied ? (
                    <Check className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3 py-2">
              <Input
                placeholder="Key name (e.g. Production API)"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
              />
            </div>
          )}
          <DialogFooter>
            {newKey ? (
              <Button
                onClick={() => {
                  setCreateKeyOpen(false);
                  setNewKey(null);
                }}
              >
                Done
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  onClick={() => setCreateKeyOpen(false)}
                >
                  Cancel
                </Button>
                <Button onClick={createApiKey} disabled={!keyName}>
                  Create
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
