#!/usr/bin/env python3
"""
Setup script for Slack integration with Invoice App

This script helps configure the Slack bot and provides setup instructions.
"""

import os
import sys
import json
from pathlib import Path

def create_slack_env_template():
    """Create environment template for Slack configuration"""
    env_template = """
# Slack Integration Configuration
SLACK_VERIFICATION_TOKEN=your_slack_verification_token_here
SLACK_BOT_TOKEN=xoxb-your-bot-token-here

# Optional: Slack App Configuration
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
SLACK_SIGNING_SECRET=your_slack_signing_secret
"""
    
    env_file = Path(__file__).parent.parent / ".env.slack"
    with open(env_file, 'w') as f:
        f.write(env_template.strip())
    
    print(f"✅ Created Slack environment template: {env_file}")
    print("📝 Please edit this file with your actual Slack app credentials")

def create_slack_app_manifest():
    """Create Slack app manifest for easy setup"""
    manifest = {
        "display_information": {
            "name": "Invoice Bot",
            "description": "Manage invoices and clients directly from Slack",
            "background_color": "#2c3e50"
        },
        "features": {
            "bot_user": {
                "display_name": "Invoice Bot",
                "always_online": True
            },
            "slash_commands": [
                {
                    "command": "/invoice",
                    "url": "https://your-domain.com/api/v1/slack/commands",
                    "description": "Manage invoices and clients",
                    "usage_hint": "create client John Doe, email: john@example.com"
                }
            ]
        },
        "oauth_config": {
            "scopes": {
                "bot": [
                    "commands",
                    "chat:write",
                    "app_mentions:read",
                    "channels:read",
                    "groups:read",
                    "im:read",
                    "im:history",
                    "mpim:read"
                ]
            }
        },
        "settings": {
            "event_subscriptions": {
                "request_url": "https://your-domain.com/api/v1/slack/events",
                "bot_events": [
                    "app_mention",
                    "message.im"
                ]
            },
            "interactivity": {
                "is_enabled": True,
                "request_url": "https://your-domain.com/api/v1/slack/interactive"
            },
            "org_deploy_enabled": False,
            "socket_mode_enabled": False,
            "token_rotation_enabled": False
        }
    }
    
    manifest_file = Path(__file__).parent.parent / "slack_app_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Created Slack app manifest: {manifest_file}")
    print("📝 Use this manifest to create your Slack app at https://api.slack.com/apps")

def print_setup_instructions():
    """Print detailed setup instructions"""
    instructions = """
🚀 Slack Integration Setup Instructions

1. CREATE SLACK APP:
   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From an app manifest"
   - Use the generated slack_app_manifest.json file
   - Or create manually with these features:
     * Bot User
     * Slash Commands (/invoice)
     * Event Subscriptions (app_mention, message.im)

2. CONFIGURE SLACK APP:
   - In "OAuth & Permissions", add these Bot Token Scopes:
     * commands
     * chat:write
     * app_mentions:read
     * channels:read
     * groups:read
     * im:read
     * im:history
     * mpim:read
   
   - In "Slash Commands", create:
     * Command: /invoice
     * Request URL: https://your-domain.com/api/v1/slack/commands
     * Description: Manage invoices and clients
   
   - In "Event Subscriptions":
     * Request URL: https://your-domain.com/api/v1/slack/events
     * Subscribe to: app_mention, message.im

3. GET CREDENTIALS:
   - Bot User OAuth Token (starts with xoxb-)
   - Verification Token (from Basic Information)
   - Signing Secret (from Basic Information)

4. CONFIGURE ENVIRONMENT:
   - Edit .env.slack with your credentials
   - Add to your main .env file:
     SLACK_VERIFICATION_TOKEN=your_token
     SLACK_BOT_TOKEN=xoxb-your-bot-token

5. DEPLOY & TEST:
   - Deploy your app with Slack integration
   - Install the Slack app to your workspace
   - Test with: /invoice help

📋 SUPPORTED COMMANDS:
   /invoice create client John Doe, email: john@example.com
   /invoice create invoice for John Doe, amount: 500
   /invoice list clients
   /invoice list invoices
   /invoice overdue invoices
   /invoice outstanding balance
   /invoice invoice stats

🔧 TROUBLESHOOTING:
   - Check logs at /api/v1/slack/health
   - Verify bot user has correct permissions
   - Ensure webhook URLs are accessible from Slack
   - Test MCP integration separately first
"""
    
    print(instructions)

def main():
    """Main setup function"""
    print("🤖 Setting up Slack Integration for Invoice App\n")
    
    # Create configuration files
    create_slack_env_template()
    create_slack_app_manifest()
    
    print()
    print_setup_instructions()
    
    print("\n✅ Setup files created successfully!")
    print("📖 Follow the instructions above to complete the integration.")

if __name__ == "__main__":
    main()