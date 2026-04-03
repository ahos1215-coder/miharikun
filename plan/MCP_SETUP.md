> **⚠️ アーカイブ文書**: このドキュメントは歴史的記録として保持されています。現在のシステム構成は `plan/HANDOFF.md` を参照してください。

# MCP Google Drive Server Setup

## Overview
The MIHARIKUN project uses an MCP (Model Context Protocol) server to access Google Drive
for PDF full-text storage.

## Configuration File

Create `.mcp.json` in the project root with the following content:

```json
{
  "mcpServers": {
    "gdrive": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-google-drive"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "${GOOGLE_SERVICE_ACCOUNT_JSON_PATH}"
      }
    }
  }
}
```

## Setup Steps

### 1. Create a Google Cloud Service Account
1. Go to https://console.cloud.google.com/
2. Create or select a project
3. Enable the Google Drive API
4. Go to IAM & Admin > Service Accounts
5. Create a service account with Drive access
6. Generate a JSON key file and download it

### 2. Store the Credentials File
Save the downloaded JSON key file to a secure location on your machine.
**Do NOT place it inside the repository** (the repo is public).

Recommended location:
```
~/.config/miharikun/google-service-account.json
```

### 3. Set the Environment Variable
Set `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` to point to the JSON key file:

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable(
  "GOOGLE_SERVICE_ACCOUNT_JSON_PATH",
  "C:\Users\<you>\.config\miharikun\google-service-account.json",
  "User"
)
```

**Linux/macOS (bash):**
```bash
export GOOGLE_SERVICE_ACCOUNT_JSON_PATH="$HOME/.config/miharikun/google-service-account.json"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

### 4. Create the .mcp.json file
Copy the JSON block from the "Configuration File" section above into `.mcp.json` at the project root.

### 5. Verify
Run Claude Code in the project directory. The MCP server should start automatically
and provide Google Drive tools.

## Security Notes
- The credentials JSON file must NEVER be committed to the repository
- The `.gitignore` should already exclude `*.json` key files in sensitive directories
- If credentials are accidentally committed, revoke them immediately in Google Cloud Console
  and generate new ones
