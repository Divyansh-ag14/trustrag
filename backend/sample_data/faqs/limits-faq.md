# Rate Limits and Storage FAQ

## What are the API rate limits?

API rate limits depend on your plan:

- **Free**: 100 requests per minute, 1,000 requests per day
- **Pro**: 1,000 requests per minute, 50,000 requests per day
- **Enterprise**: 5,000 requests per minute, unlimited daily requests

Note: Prior to AcmeSaaS v3.2, Enterprise plans had a 10,000 requests per minute limit. This was reduced to 5,000 in v3.2 to improve platform stability. Affected Enterprise customers can request a temporary rate limit increase through their account manager.

Rate limit headers are included in all API responses:
- `X-RateLimit-Limit`: Maximum requests allowed in the window
- `X-RateLimit-Remaining`: Requests remaining in the current window
- `X-RateLimit-Reset`: Unix timestamp when the window resets

When rate limited, the API returns HTTP 429 with a `Retry-After` header.

## What are the storage limits?

- **Free**: 100 MB total workspace storage
- **Pro**: 10 GB per user (e.g., 10 users = 100 GB)
- **Enterprise**: Unlimited storage

Storage is consumed by file attachments on tasks, project assets, and uploaded documents. Text content (tasks, comments, descriptions) does not count toward storage limits.

## How many projects can I create?

- **Free**: 3 projects
- **Pro**: Unlimited
- **Enterprise**: Unlimited

## How many users can I have?

- **Free**: 5 users
- **Pro**: Unlimited (billed per user)
- **Enterprise**: Unlimited (custom pricing)

## Are there limits on task history or audit logs?

- **Free**: 30 days of activity history
- **Pro**: 1 year of activity history
- **Enterprise**: Unlimited history with full audit logs

## What are the webhook limits?

- **Free**: No webhooks
- **Pro**: 10 webhook endpoints per workspace
- **Enterprise**: 50 webhook endpoints per workspace

Each webhook endpoint can subscribe to a maximum of 20 event types.

## What are the file upload limits?

Maximum file size per upload:
- **Free**: 10 MB
- **Pro**: 50 MB
- **Enterprise**: 100 MB

Supported file types: Images (PNG, JPG, GIF, SVG), Documents (PDF, DOCX, XLSX, PPTX), Code files, Text files, ZIP archives (up to 200 MB on Enterprise).
