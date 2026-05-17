# Troubleshooting Integration Issues

## Slack Integration Not Sending Notifications

### Symptoms
- Tasks are created and updated in AcmeSaaS but no notifications appear in Slack
- The integration shows as "Connected" in Settings

### Solutions
1. **Check channel selection**: Go to Settings > Integrations > Slack and verify that at least one channel is selected for notifications
2. **Check notification preferences**: Ensure the event types you expect (task.created, task.completed, etc.) are enabled
3. **Re-authorize**: If notifications stopped working after a Slack workspace update, disconnect and reconnect the integration
4. **Check Slack permissions**: Ensure the AcmeSaaS Slack app hasn't been restricted by your Slack admin. Ask your Slack admin to check Apps > Manage > AcmeSaaS

## Jira Integration Not Syncing

### Symptoms
- Tasks created in AcmeSaaS are not appearing in Jira (or vice versa)
- Sync was working before but stopped
- Error message: "Jira sync failed: OAuth token expired"

### Solutions
1. **Re-authorize after v3.2 update**: AcmeSaaS v3.2 changed the Jira OAuth scope requirements. Go to Settings > Integrations > Jira and click "Reconnect" to re-authorize with the new scopes
2. **Check project mapping**: Verify that the AcmeSaaS project is mapped to the correct Jira project under Settings > Integrations > Jira > Project Mappings
3. **Verify Jira Cloud**: The AcmeSaaS Jira integration only supports Jira Cloud. Jira Server and Data Center are not supported
4. **Check sync direction**: If sync is set to "one-way," changes in the non-primary direction will not sync. Update to "two-way" if needed
5. **Rate limits**: Jira has its own API rate limits. If you're syncing a large number of tasks, some may be delayed. Check Settings > Integrations > Jira > Sync Log for failed items

## GitHub Integration Not Linking PRs

### Symptoms
- Pull requests are not appearing on task cards
- Commits with task IDs are not being linked

### Solutions
1. **Check branch naming**: Use the format `ACME-123-description` where `ACME-123` is the task ID. The task ID must appear in the branch name, commit message, or PR title
2. **Verify GitHub App installation**: Go to your GitHub organization settings > Installed GitHub Apps and ensure AcmeSaaS has access to the relevant repositories
3. **Check repository mapping**: Go to Settings > Integrations > GitHub and verify the repository is mapped to the correct AcmeSaaS project

## Webhook Delivery Failures

### Symptoms
- Webhook events are not being received by your endpoint
- Settings > Integrations > Webhooks shows failed deliveries

### Solutions
1. **Check endpoint URL**: Ensure the URL is publicly accessible and returns HTTP 200 for POST requests
2. **Check SSL**: Webhook endpoints must use HTTPS. Self-signed certificates are not accepted
3. **Check response time**: Endpoints must respond within 10 seconds or the delivery is marked as failed
4. **Check payload size**: Some events can produce large payloads. Ensure your endpoint can handle up to 1 MB request bodies
5. **Manual retry**: Click "Retry" on any failed delivery in the webhook log to resend it
