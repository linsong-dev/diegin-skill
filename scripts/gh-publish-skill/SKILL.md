---
name: gh-publish
description: "Publish or update Codex skills to GitHub. Use when the user asks to: push code to GitHub, create a repository, make a release, set repository topics, update a GitHub repo, or login to GitHub for publishing. Covers the full workflow: browser-based GitHub login via Edge CDP, git push, release creation, topic management, and pre-push audit."
---

# GitHub Publish Skill

Automate publishing/updating Codex skill repositories on GitHub.

## Prerequisites

- **Edge browser** installed at known path (configurable)
- **Git** available (`git --version`)
- **Python** with `websocket`, `requests` packages
- **Network proxy** (default: `http://127.0.0.1:3067`; configurable)

## Workflow

### 0. Audit (always run before push)

```powershell
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py audit --dir S:\diegin-skill
```

Checks for:
- UTF-8 encoding validity
- UTF-8 BOM (Byte Order Mark)
- Replacement characters (\\ufffd)
- Garbled text (excessive ? marks)
Returns exit code 0 if clean, 1 if issues found.

### 1. Login & Get Token

```powershell
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py login
```

### 2. Push Code Changes

```powershell
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py push ^
  --owner diegin-skill --repo diegin ^
  --message "Update: added new feature" ^
  --dir S:\diegin-skill
```

### 3. Create Release

```powershell
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py release ^
  --owner diegin-skill --repo diegin ^
  --tag v1.1.0 --name "v1.1.0 - New Features" ^
  --body "## Changelog\n\n- Feature A\n- Bug fix B"
```

### 4. Set Repository Topics

```powershell
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py topics ^
  --owner diegin-skill --repo diegin ^
  --topics codex codex-skill ai-agent self-evolving dgen
```

## Full Update Example

```powershell
# 0. Audit
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py audit ^
  --dir S:\diegin-skill

# 1. Login (first time only)
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py login

# 2. Push changes
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py push ^
  --owner diegin-skill --repo diegin ^
  --message "v1.1.0 update" --dir S:\diegin-skill

# 3. Create release
python S:\diegin-skill\scripts\gh-publish-skill\scripts\gh_publish.py release ^
  --owner diegin-skill --repo diegin ^
  --tag v1.1.0 --name "v1.1.0" --body "## Changelog"
```

## Troubleshooting

| Issue | Fix |
|:---|:---|
| Audit finds issues | Fix reported files, re-run audit |
| "No token" | Run `login` first |
| Token expired | Delete `.gh_token` file, re-run `login` |
| Edge won't start | Check `EDGE_PATH` in script |
| Git push timeout | Check proxy config in `PROXY` var |

## Configuration

Edit `scripts/gh_publish.py` top section:

```python
PROXY = "http://127.0.0.1:3067"       # Network proxy
EDGE_DEBUG_PORT = 9222                 # CDP debug port
EDGE_PATH = r"D:\path\to\msedge.exe"   # Edge executable
TOKEN_FILE = ".../.gh_token"           # Saved token path
```
