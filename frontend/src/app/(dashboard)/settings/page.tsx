"use client";

import { Settings, Users, Key } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { useAuthStore } from "@/stores/auth-store";

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);

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
          <TabsTrigger value="api-keys" className="text-xs gap-1.5">
            <Key className="h-3 w-3" />
            API Keys
          </TabsTrigger>
        </TabsList>

        <TabsContent value="workspace" className="mt-4 space-y-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader>
              <CardTitle className="text-sm">General</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Workspace name</label>
                <Input placeholder="My Workspace" disabled />
              </div>
              <Separator className="opacity-40" />
              <div className="space-y-2">
                <label className="text-sm font-medium">Your profile</label>
                <div className="grid grid-cols-2 gap-3">
                  <Input value={user?.name || ""} disabled placeholder="Name" />
                  <Input value={user?.email || ""} disabled placeholder="Email" />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="mt-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">Team members</CardTitle>
              <Button size="sm" disabled>
                Invite user
              </Button>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Users className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                  User management coming soon
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="api-keys" className="mt-4">
          <Card className="border-border/40 bg-card/50">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">API Keys</CardTitle>
              <Button size="sm" disabled>
                Create key
              </Button>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Key className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                  API key management coming soon
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
