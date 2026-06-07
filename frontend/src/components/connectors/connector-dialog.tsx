"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Connector, ConnectorCreate } from "@/types/api";

interface ConnectorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: ConnectorCreate) => Promise<void>;
  onTest?: (data: ConnectorCreate) => Promise<{ success: boolean; message: string }>;
  editConnector?: Connector | null;
}

type ConnectorType = "notion" | "github" | "web_scraper";

const TYPE_OPTIONS: { value: ConnectorType; label: string; description: string }[] = [
  { value: "notion", label: "Notion", description: "Sync pages and databases from Notion" },
  { value: "github", label: "GitHub", description: "Import docs, issues, and wikis from GitHub" },
  { value: "web_scraper", label: "Web Scraper", description: "Crawl and index web pages" },
];

export function ConnectorDialog({
  open,
  onOpenChange,
  onSubmit,
  onTest,
  editConnector,
}: ConnectorDialogProps) {
  const [step, setStep] = useState<"type" | "config">(editConnector ? "config" : "type");
  const [connectorType, setConnectorType] = useState<ConnectorType>("notion");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Credentials
  const [apiToken, setApiToken] = useState("");

  // Notion config
  const [notionPageIds, setNotionPageIds] = useState("");
  const [notionDatabaseId, setNotionDatabaseId] = useState("");

  // GitHub config
  const [githubOwner, setGithubOwner] = useState("");
  const [githubRepo, setGithubRepo] = useState("");
  const [githubPaths, setGithubPaths] = useState("");
  const [githubIncludeIssues, setGithubIncludeIssues] = useState(true);

  // Web scraper config
  const [baseUrl, setBaseUrl] = useState("");
  const [maxDepth, setMaxDepth] = useState("2");
  const [maxPages, setMaxPages] = useState("50");
  const [cssSelector, setCssSelector] = useState("");

  // Sync settings
  const [syncEnabled, setSyncEnabled] = useState(false);
  const [syncInterval, setSyncInterval] = useState("24");

  useEffect(() => {
    if (editConnector) {
      setConnectorType(editConnector.connector_type);
      setName(editConnector.name);
      setSyncEnabled(editConnector.sync_enabled);
      setSyncInterval(String(editConnector.sync_interval_hours));

      const config = editConnector.config || {};
      if (editConnector.connector_type === "notion") {
        setNotionPageIds((config.page_ids as string[] || []).join(", "));
        setNotionDatabaseId((config.database_id as string) || "");
      } else if (editConnector.connector_type === "github") {
        setGithubOwner((config.owner as string) || "");
        setGithubRepo((config.repo as string) || "");
        setGithubPaths(((config.paths as string[]) || []).join(", "));
        setGithubIncludeIssues(config.include_issues !== false);
      } else if (editConnector.connector_type === "web_scraper") {
        setBaseUrl((config.base_url as string) || "");
        setMaxDepth(String(config.max_depth || 2));
        setMaxPages(String(config.max_pages || 50));
        setCssSelector((config.css_selector as string) || "");
      }
      setStep("config");
    } else {
      resetForm();
    }
  }, [editConnector, open]);

  function resetForm() {
    setStep("type");
    setConnectorType("notion");
    setName("");
    setApiToken("");
    setNotionPageIds("");
    setNotionDatabaseId("");
    setGithubOwner("");
    setGithubRepo("");
    setGithubPaths("");
    setGithubIncludeIssues(true);
    setBaseUrl("");
    setMaxDepth("2");
    setMaxPages("50");
    setCssSelector("");
    setSyncEnabled(false);
    setSyncInterval("24");
    setTestResult(null);
  }

  function buildPayload(): ConnectorCreate {
    const credentials: Record<string, string> = {};
    const config: Record<string, unknown> = {};

    if (connectorType === "notion") {
      credentials.token = apiToken.trim();
      if (notionPageIds.trim()) {
        config.page_ids = notionPageIds.split(",").map((s) => s.trim()).filter(Boolean);
      }
      if (notionDatabaseId.trim()) {
        config.database_id = notionDatabaseId.trim();
      }
    } else if (connectorType === "github") {
      credentials.token = apiToken.trim();
      config.owner = githubOwner.trim();
      config.repo = githubRepo.trim();
      if (githubPaths.trim()) {
        config.paths = githubPaths.split(",").map((s) => s.trim()).filter(Boolean);
      }
      config.include_issues = githubIncludeIssues;
    } else if (connectorType === "web_scraper") {
      if (apiToken.trim()) {
        credentials.token = apiToken;
      }
      config.base_url = baseUrl;
      config.max_depth = parseInt(maxDepth) || 2;
      config.max_pages = parseInt(maxPages) || 50;
      if (cssSelector.trim()) {
        config.css_selector = cssSelector;
      }
    }

    return {
      name,
      connector_type: connectorType,
      credentials,
      config,
      sync_enabled: syncEnabled,
      sync_interval_hours: parseInt(syncInterval) || 24,
    };
  }

  async function handleTest() {
    if (!onTest) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(buildPayload());
      setTestResult(result);
    } catch {
      setTestResult({ success: false, message: "Test request failed" });
    } finally {
      setTesting(false);
    }
  }

  async function handleSubmit() {
    setSaving(true);
    try {
      await onSubmit(buildPayload());
      onOpenChange(false);
      resetForm();
    } catch {
      // handled upstream
    } finally {
      setSaving(false);
    }
  }

  const isValid = () => {
    if (!name.trim()) return false;
    if (connectorType === "notion" && !apiToken.trim() && !editConnector) return false;
    if (connectorType === "github" && (!githubOwner.trim() || !githubRepo.trim())) return false;
    if (connectorType === "github" && !apiToken.trim() && !editConnector) return false;
    if (connectorType === "web_scraper" && !baseUrl.trim()) return false;
    return true;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {editConnector ? "Edit connector" : step === "type" ? "Add connector" : `New ${TYPE_OPTIONS.find(t => t.value === connectorType)?.label} connector`}
          </DialogTitle>
          <DialogDescription>
            {step === "type"
              ? "Choose a data source to connect"
              : "Configure your connector settings"}
          </DialogDescription>
        </DialogHeader>

        {step === "type" && !editConnector && (
          <div className="space-y-2 py-2">
            {TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setConnectorType(opt.value);
                  setStep("config");
                }}
                className="w-full flex items-center gap-3 p-3 rounded-lg border border-border/40 hover:bg-muted/30 transition-colors text-left"
              >
                <div>
                  <p className="text-sm font-medium">{opt.label}</p>
                  <p className="text-xs text-muted-foreground">{opt.description}</p>
                </div>
              </button>
            ))}
          </div>
        )}

        {step === "config" && (
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Name</label>
              <Input
                placeholder="e.g. Product Docs"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            {/* Credentials */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                {connectorType === "web_scraper" ? "Auth token (optional)" : "API Token"}
              </label>
              <Input
                type="password"
                placeholder={editConnector ? "Leave blank to keep existing" : "Enter token"}
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
              />
            </div>

            {/* Type-specific config */}
            {connectorType === "notion" && (
              <>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Page IDs</label>
                  <Input
                    placeholder="Comma-separated page IDs"
                    value={notionPageIds}
                    onChange={(e) => setNotionPageIds(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Find page IDs in the Notion page URL
                  </p>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Database ID (optional)</label>
                  <Input
                    placeholder="Notion database ID"
                    value={notionDatabaseId}
                    onChange={(e) => setNotionDatabaseId(e.target.value)}
                  />
                </div>
              </>
            )}

            {connectorType === "github" && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Owner</label>
                    <Input
                      placeholder="org or user"
                      value={githubOwner}
                      onChange={(e) => setGithubOwner(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Repository</label>
                    <Input
                      placeholder="repo-name"
                      value={githubRepo}
                      onChange={(e) => setGithubRepo(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Paths (optional)</label>
                  <Input
                    placeholder="docs/, README.md"
                    value={githubPaths}
                    onChange={(e) => setGithubPaths(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Comma-separated paths to sync. Leave blank for entire repo.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={githubIncludeIssues}
                    onChange={(e) => setGithubIncludeIssues(e.target.checked)}
                    className="rounded border-border"
                  />
                  Include open issues
                </label>
              </>
            )}

            {connectorType === "web_scraper" && (
              <>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Base URL</label>
                  <Input
                    placeholder="https://docs.example.com"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Max depth</label>
                    <Input
                      type="number"
                      min="1"
                      max="5"
                      value={maxDepth}
                      onChange={(e) => setMaxDepth(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Max pages</label>
                    <Input
                      type="number"
                      min="1"
                      max="200"
                      value={maxPages}
                      onChange={(e) => setMaxPages(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">CSS selector (optional)</label>
                  <Input
                    placeholder="article, main, .content"
                    value={cssSelector}
                    onChange={(e) => setCssSelector(e.target.value)}
                  />
                </div>
              </>
            )}

            {/* Sync settings */}
            <div className="border-t border-border/40 pt-4 space-y-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={syncEnabled}
                  onChange={(e) => setSyncEnabled(e.target.checked)}
                  className="rounded border-border"
                />
                Enable automatic sync
              </label>
              {syncEnabled && (
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">Sync interval (hours)</label>
                  <Input
                    type="number"
                    min="1"
                    max="168"
                    value={syncInterval}
                    onChange={(e) => setSyncInterval(e.target.value)}
                  />
                </div>
              )}
            </div>

            {/* Test result */}
            {testResult !== null && (
              <div className={`text-xs px-3 py-2 rounded-md ${testResult.success ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                {testResult.message || (testResult.success ? "Connection successful" : "Connection failed")}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {step === "config" && !editConnector && (
            <Button variant="outline" onClick={() => { setStep("type"); setTestResult(null); }}>
              Back
            </Button>
          )}
          {step === "config" && onTest && (
            <Button variant="outline" onClick={handleTest} disabled={testing || !isValid()}>
              {testing ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
              Test
            </Button>
          )}
          {step === "config" && (
            <Button onClick={handleSubmit} disabled={saving || !isValid()}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : null}
              {editConnector ? "Save" : "Create"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
