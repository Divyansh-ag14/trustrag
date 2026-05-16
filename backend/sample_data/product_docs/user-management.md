# User Management

Manage team members, roles, and permissions within your AcmeSaaS workspace.

## Roles

AcmeSaaS has three built-in roles:

### Owner
- Full access to all workspace settings, billing, and data
- Can delete the workspace
- Can transfer ownership to another admin
- Each workspace has exactly one owner

### Admin
- Can manage users (invite, remove, change roles)
- Can manage all projects and settings
- Can access billing information (but cannot change the plan)
- Can configure integrations
- Can view audit logs

### Member
- Can create and manage projects they own
- Can be assigned tasks in any project they have access to
- Can view and comment on tasks in projects they belong to
- Cannot access workspace settings or billing
- Cannot invite new users (unless the workspace setting "Members can invite" is enabled)

### Viewer (Enterprise only)
- Read-only access to assigned projects
- Can view tasks and comments but cannot edit
- Can add comments if the project setting allows it
- Useful for stakeholders and external collaborators

## Inviting Users

1. Go to Settings > Users
2. Click "Invite User"
3. Enter the email address
4. Select a role (Admin or Member)
5. Optionally assign them to specific projects
6. Click "Send Invite"

The invited user receives an email with a link to join. Invitations expire after 7 days.

### Bulk Invites
Enterprise customers can upload a CSV file to invite multiple users at once. The CSV format should be:
```
email,role,projects
jane@company.com,member,"Project A, Project B"
john@company.com,admin,
```

## Removing Users

1. Go to Settings > Users
2. Find the user and click the three-dot menu
3. Select "Remove from workspace"
4. Choose whether to reassign their tasks or leave them unassigned
5. Confirm removal

Removed users lose access immediately. Their past comments and activity remain in the audit log.

## SSO Configuration

Single Sign-On is available on Pro (Google and Microsoft only) and Enterprise (full SAML/SSO) plans.

### Google SSO (Pro and Enterprise)
1. Go to Settings > Security > SSO
2. Select "Google"
3. Enter your Google Workspace domain
4. Users with matching email domains can sign in with Google

### Microsoft SSO (Pro and Enterprise)
1. Go to Settings > Security > SSO
2. Select "Microsoft"
3. Enter your Azure AD tenant ID
4. Users with matching email domains can sign in with Microsoft

### SAML SSO (Enterprise only)
1. Go to Settings > Security > SSO
2. Select "SAML"
3. Enter your Identity Provider (IdP) metadata URL or upload the metadata XML
4. Configure attribute mappings (email, name, role)
5. Enable "Enforce SSO" to require all users to sign in via SSO

When SSO enforcement is enabled, password-based login is disabled for all non-owner accounts.
