# API Authentication

AcmeSaaS uses API keys for programmatic access. All API requests must include authentication.

## Generating an API Key

1. Go to Settings > API Keys
2. Click "Create API Key"
3. Enter a name for the key (e.g., "CI/CD Pipeline", "Data Export Script")
4. Select permissions:
   - **Read**: View tasks, projects, users, and comments
   - **Write**: Create and update tasks, projects, and comments
   - **Admin**: Manage users, settings, and integrations
5. Click "Generate"
6. Copy the key immediately — it is only shown once

API keys follow the format: `acme_sk_live_xxxxxxxxxxxxxxxxxxxx`

## Using the API Key

Include the API key in the `Authorization` header of every request:

```
Authorization: Bearer acme_sk_live_xxxxxxxxxxxxxxxxxxxx
```

## OAuth 2.0 (Enterprise)

Enterprise customers can use OAuth 2.0 for user-level API access:

1. Register an OAuth application in Settings > API > OAuth Apps
2. Redirect users to: `https://app.acmesaas.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=read,write`
3. Exchange the authorization code for an access token at `POST /oauth/token`
4. Access tokens expire after 1 hour. Use the refresh token to obtain new access tokens.

## Rate Limits

API rate limits are enforced per API key:
- Free: 100 req/min
- Pro: 1,000 req/min
- Enterprise: 5,000 req/min (reduced from 10,000 in v3.2)

Exceeding the rate limit returns HTTP 429. Check the `X-RateLimit-Remaining` header to track usage.

## Error Responses

All API errors return a consistent JSON format:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "You have exceeded the rate limit. Please retry after 60 seconds.",
    "status": 429
  }
}
```

Common error codes:
- `unauthorized` (401): Invalid or missing API key
- `forbidden` (403): API key does not have required permissions
- `not_found` (404): Resource does not exist or is not accessible
- `rate_limit_exceeded` (429): Too many requests
- `internal_error` (500): Server error, please retry
