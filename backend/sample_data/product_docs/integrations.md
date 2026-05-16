# Integrations

AcmeSaaS integrates with the tools your team already uses. All integrations are managed from Settings > Integrations.

## Slack Integration

Connect AcmeSaaS to Slack to receive notifications and create tasks from messages.

### Setup
1. Go to Settings > Integrations > Slack
2. Click "Connect to Slack"
3. Authorize the OAuth connection in the Slack popup
4. Select which Slack channels should receive notifications
5. Configure notification preferences (task created, completed, commented, etc.)

### Features
- Receive task notifications in Slack channels
- Create tasks directly from Slack messages using the `/acme create` command
- Link Slack threads to task comments
- Get daily digest summaries in a channel of your choice

### Permissions Required
- Post to channels
- Read channel messages (for task creation)
- Add shortcuts and slash commands

## Jira Integration

Sync projects and issues between AcmeSaaS and Jira for teams transitioning or using both tools.

### Setup
1. Go to Settings > Integrations > Jira
2. Click "Connect to Jira"
3. Enter your Jira instance URL (e.g., yourcompany.atlassian.net)
4. Authorize via OAuth 2.0
5. Map AcmeSaaS projects to Jira projects
6. Configure sync direction (one-way or two-way)

### Sync Behavior
- New tasks in AcmeSaaS create corresponding Jira issues (and vice versa if two-way)
- Status changes sync automatically with a 30-second delay
- Comments sync bidirectionally
- Attachments are not synced (limitation of the Jira API)

### Important Notes
- The Jira integration requires Jira Cloud (Server/Data Center is not supported)
- OAuth scopes were updated in AcmeSaaS v3.2 — if you connected before v3.2, you need to re-authorize
- Maximum 10 project mappings per workspace on Pro plan, unlimited on Enterprise

## GitHub Integration

Link GitHub repositories to AcmeSaaS projects for development tracking.

### Setup
1. Go to Settings > Integrations > GitHub
2. Click "Connect to GitHub"
3. Install the AcmeSaaS GitHub App on your organization
4. Select which repositories to link
5. Map repositories to AcmeSaaS projects

### Features
- Link pull requests and commits to tasks using task IDs in branch names or commit messages
- Automatic task status updates when PRs are merged
- View PR status and CI checks directly on task cards
- Create tasks from GitHub issues

## Webhook Integration

Send real-time event data to any external service using webhooks.

### Setup
1. Go to Settings > Integrations > Webhooks
2. Click "Add Webhook"
3. Enter the destination URL
4. Select which events to send (task.created, task.updated, task.completed, comment.added, etc.)
5. Optionally add a secret key for HMAC signature verification

### Webhook Payload
All webhooks send JSON payloads with:
- `event`: The event type
- `timestamp`: ISO 8601 timestamp
- `data`: Event-specific data including the full object
- `workspace_id`: Your workspace identifier

### Retry Policy
Failed webhook deliveries are retried 3 times with exponential backoff (1 min, 5 min, 15 min). After 3 failures, the webhook is disabled and an admin notification is sent.
