import pytest


@pytest.fixture
def sample_text():
    return """# Getting Started with AcmeSaaS

AcmeSaaS is a B2B project management tool designed for teams of all sizes.

## Quick Setup

1. Create your workspace at app.acmesaas.com
2. Invite your team members via Settings > Users
3. Create your first project using a template or from scratch

## Key Features

AcmeSaaS offers task management, reporting, integrations, and API access.
Each feature is designed to help teams collaborate more effectively.

## Support

For help, contact support@acmesaas.com or visit our help center.
"""
