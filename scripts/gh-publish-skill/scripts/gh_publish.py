#!/usr/bin/env python3
"""
gh_publish.py - GitHub Publish/Update Automation for Codex Skills
===============================================================
Handles: login, push, release creation, topic setting.
Requires: Edge browser with GitHub login session active.
"""

import json, os, sys, time, base64, re, subprocess
import urllib.request
import websocket

# ─── CONFIG ──────────────────────────────────────────────────────────
PROXY = "http://127.0.0.1:3067"
EDGE_DEBUG_PORT = 9222
EDGE_PATH = r"D:\Soft\浏览器\MSEDGE\Chrome-bin\146.0.3856.97\msedge.exe"
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", ".gh_token")
REPO_DIR = os.path.join(os.path.dirname(__file__), "..")  # default: parent of scripts/

# ─── HELPERS ─────────────────────────────────────────────────────────

def log(msg):
    print(f"[gh-publish] {msg}")

def assert_edge_running():
    """Ensure Edge is running with CDP debug port."""
    try:
        targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json", timeout=5).read())
        log(f"Edge OK ({len(targets)} targets)")
        return targets
    except Exception:
        log("Starting Edge with CDP...")
        subprocess.Popen([
            EDGE_PATH,
            f"--remote-debugging-port={EDGE_DEBUG_PORT}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--new-window",
            "https://github.com"
        ])
        time.sleep(5)
        return assert_edge_running()

def get_ws_url(targets, url_filter=None):
    """Get WebSocket URL for a matching page target."""
    for t in targets:
        if t["type"] == "page":
            if url_filter is None or url_filter in t["url"]:
                return "ws://127.0.0.1:9222/devtools/page/" + t["id"]
    # Fallback to first page
    for t in targets:
        if t["type"] == "page":
            return "ws://127.0.0.1:9222/devtools/page/" + t["id"]
    raise RuntimeError("No page target found")

class CDP:
    """Chrome DevTools Protocol wrapper."""
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=10)
        self.msg_id = 0
    
    def cmd(self, method, params=None):
        self.msg_id += 1
        cmd = {"id": self.msg_id, "method": method}
        if params:
            cmd["params"] = params
        self.ws.send(json.dumps(cmd))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == self.msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})
    
    def js(self, code):
        """Evaluate JavaScript and return result value."""
        r = self.cmd("Runtime.evaluate", {
            "expression": code,
            "awaitPromise": True
        })
        return r.get("result", {}).get("value", "")
    
    def close(self):
        self.ws.close()

def get_cookies_via_cdp(cdp):
    """Extract GitHub session cookies from browser."""
    result = cdp.cmd("Network.getAllCookies")
    cookies = {}
    for c in result.get("cookies", []):
        if "github" in c.get("domain", ""):
            cookies[c["name"]] = c["value"]
    return cookies

def read_token():
    """Read saved token or None."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return None

def save_token(token):
    """Save token for reuse."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    log("Token saved")

def api_call(method, path, data=None, token=None):
    """Make authenticated GitHub API call through proxy."""
    import requests
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "gh-publish-skill"
    }
    if token:
        headers["Authorization"] = f"token {token}"
    
    proxies = {"http": PROXY, "https": PROXY}
    url = f"https://api.github.com{path}"
    
    if method == "GET":
        r = requests.get(url, headers=headers, proxies=proxies, timeout=30)
    elif method == "POST":
        r = requests.post(url, json=data, headers=headers, proxies=proxies, timeout=30)
    elif method == "PATCH":
        r = requests.patch(url, json=data, headers=headers, proxies=proxies, timeout=30)
    elif method == "PUT":
        r = requests.put(url, json=data, headers=headers, proxies=proxies, timeout=30)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return r.status_code, r.json() if r.text else {}

def ensure_token(cdp):
    """Create a GitHub PAT via browser if none saved."""
    token = read_token()
    if token:
        # Verify token works
        status, _ = api_call("GET", "/user", token=token)
        if status == 200:
            log("Token valid, using saved token")
            return token
        log("Saved token expired, creating new one...")
    
    # Navigate to token creation page
    cdp.cmd("Page.navigate", {"url": "https://github.com/settings/tokens/new"})
    time.sleep(4)
    
    # Fill token name
    cdp.js("""
    var inp = document.querySelector("#oauth_access_description");
    if (inp) {
        inp.value = "gh-publish-skill";
        inp.dispatchEvent(new Event("input", {bubbles: true}));
        inp.dispatchEvent(new Event("change", {bubbles: true}));
    }
    """)
    time.sleep(1)
    
    # Check repo scope
    cdp.js("""
    var labels = document.querySelectorAll("label");
    for (var i = 0; i < labels.length; i++) {
        if (labels[i].textContent.trim().indexOf("repo") === 0) {
            var cb = labels[i].querySelector("input[type=checkbox]");
            if (cb) { cb.checked = true; cb.dispatchEvent(new Event("change", {bubbles: true})); }
            break;
        }
    }
    """)
    time.sleep(1)
    
    # Click Generate token
    cdp.js("""
    var btns = document.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) {
        if (btns[i].textContent.trim().indexOf("Generate token") >= 0) {
            btns[i].click(); break;
        }
    }
    """)
    time.sleep(4)
    
    # Extract token value
    token_val = cdp.js("""
    (function() {
        var inputs = document.querySelectorAll("input");
        for (var i = 0; i < inputs.length; i++) {
            var v = inputs[i].value;
            if (v && (v.startsWith("ghp_") || v.startsWith("github_pat_"))) return v;
        }
        var body = document.body.innerText;
        var lines = body.split("\\n");
        for (var j = 0; j < lines.length; j++) {
            var line = lines[j].trim();
            if (line.startsWith("ghp_") || line.startsWith("github_pat_")) return line;
        }
        return "";
    })()
    """)
    
    if token_val:
        save_token(token_val)
        return token_val
    raise RuntimeError("Failed to create token")

def git_ensure_remote(repo_dir, owner, repo_name, token):
    """Ensure git remote is configured with token auth."""
    orig = os.getcwd()
    os.chdir(repo_dir)
    try:
        # Check if remote exists
        r = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
        url = f"https://{owner}:{token}@github.com/{owner}/{repo_name}.git"
        
        if "origin" not in r.stdout:
            subprocess.run(["git", "remote", "add", "origin", url], check=True)
        else:
            subprocess.run(["git", "remote", "set-url", "origin", url], check=True)
        
        # Set git proxy
        subprocess.run(["git", "config", "http.proxy", PROXY], capture_output=True)
        subprocess.run(["git", "config", "https.proxy", PROXY], capture_output=True)
    finally:
        os.chdir(orig)

def git_push(repo_dir, message):
    """Add, commit, and push changes."""
    orig = os.getcwd()
    os.chdir(repo_dir)
    try:
        # Set env proxy
        env = os.environ.copy()
        env["HTTP_PROXY"] = PROXY
        env["HTTPS_PROXY"] = PROXY
        
        log("Git: adding files...")
        subprocess.run(["git", "add", "-A"], check=True, env=env)
        
        # Check if there are changes
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, env=env)
        if not r.stdout.strip():
            log("No changes to commit")
            return False
        
        log(f"Git: committing...")
        subprocess.run(["git", "commit", "-m", message], check=True, env=env)
        
        log("Git: pushing...")
        subprocess.run(["git", "push", "-u", "origin", "HEAD"], check=True, env=env, timeout=120)
        log("Push successful!")
        return True
    except subprocess.TimeoutExpired:
        log("Push timed out, but may have succeeded. Check manually.")
        return True
    finally:
        os.chdir(orig)

def git_tag_and_push(repo_dir, tag, message):
    """Create and push a tag."""
    orig = os.getcwd()
    os.chdir(repo_dir)
    try:
        env = os.environ.copy()
        env["HTTP_PROXY"] = PROXY
        env["HTTPS_PROXY"] = PROXY
        subprocess.run(["git", "tag", "-a", tag, "-m", message], check=True, env=env)
        subprocess.run(["git", "push", "origin", tag], check=True, env=env, timeout=60)
        log(f"Tag {tag} pushed")
    finally:
        os.chdir(orig)

# ─── COMMANDS ─────────────────────────────────────────────────────────

def cmd_push(owner, repo, message):
    """Push latest changes to GitHub."""
    token = read_token()
    if not token:
        raise RuntimeError("No token. Run `login` first.")
    
    git_ensure_remote(REPO_DIR, owner, repo, token)
    changed = git_push(REPO_DIR, message)
    return changed

def cmd_release(owner, repo, tag, name, body, prerelease=False):
    """Create a GitHub Release."""
    token = read_token()
    if not token:
        raise RuntimeError("No token")
    
    # Ensure tag exists
    git_ensure_remote(REPO_DIR, owner, repo, token)
    git_tag_and_push(REPO_DIR, tag, name)
    
    status, data = api_call("POST", f"/repos/{owner}/{repo}/releases", {
        "tag_name": tag,
        "target_commitish": "main",
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": prerelease
    }, token=token)
    
    if status == 201:
        log(f"Release created: {data.get('html_url', '')}")
        return data.get("html_url", "")
    raise RuntimeError(f"Release failed ({status}): {data}")

def cmd_set_topics(owner, repo, topics):
    """Set repository topics."""
    token = read_token()
    if not token:
        raise RuntimeError("No token")
    
    status, data = api_call("PUT", f"/repos/{owner}/{repo}/topics", 
                          {"names": topics}, token=token)
    if status == 200:
        log(f"Topics set: {data.get('names', [])}")
    else:
        log(f"Topics failed ({status})")

def cmd_login():
    """Interactive login via browser."""
    targets = assert_edge_running()
    ws_url = get_ws_url(targets)
    cdp = CDP(ws_url)
    try:
        # Check if already logged in
        logged = cdp.js("document.cookie.indexOf('logged_in=yes') >= 0")
        if logged:
            log("Already logged in to GitHub")
        else:
            cdp.cmd("Page.navigate", {"url": "https://github.com/login"})
            log("Please log in to GitHub in the browser window, then press Enter...")
            input()
        
        token = ensure_token(cdp)
        return token
    finally:
        cdp.close()


def cmd_audit(repo_dir):
    """Audit repo directory for encoding issues (UTF-8, BOM, mojibake, garbled text)."""
    issues = []
    ok = 0
    skipped = 0
    
    # === Mojibake detection config ===
    # Characters that are STRONG indicators of garbled UTF-8 (Latin-1 misinterpretation)
    # These appear when UTF-8 bytes are read as Latin-1 then re-encoded
    STRONG_MOJIBAKE = {
        0x00c0, 0x00c1, 0x00c2, 0x00c3, 0x00c4, 0x00c5, 0x00c6, 0x00c7,
        0x00c8, 0x00c9, 0x00ca, 0x00cb, 0x00cc, 0x00cd, 0x00ce, 0x00cf,
        0x00d0, 0x00d1, 0x00d2, 0x00d3, 0x00d4, 0x00d5, 0x00d6, 0x00d7,
        0x00d8, 0x00d9, 0x00da, 0x00db, 0x00dc, 0x00dd, 0x00de, 0x00df,
        0x00e0, 0x00e1, 0x00e2, 0x00e3, 0x00e4, 0x00e5, 0x00e6, 0x00e7,
        0x00e8, 0x00e9, 0x00ea, 0x00eb, 0x00ec, 0x00ed, 0x00ee, 0x00ef,
        0x00f0, 0x00f1, 0x00f2, 0x00f3, 0x00f4, 0x00f5, 0x00f6, 0x00f7,
        0x00f8, 0x00f9, 0x00fa, 0x00fb, 0x00fc, 0x00fd, 0x00fe, 0x00ff,
        0x00a0, 0x00a1, 0x00a2, 0x00a3, 0x00a4, 0x00a5, 0x00a6, 0x00a7,
        0x00a8, 0x00a9, 0x00aa, 0x00ab, 0x00ac, 0x00ad, 0x00ae, 0x00af,
        0x00b0, 0x00b1, 0x00b2, 0x00b3, 0x00b4, 0x00b5, 0x00b6, 0x00b7,
        0x00b8, 0x00b9, 0x00ba, 0x00bb, 0x00bc, 0x00bd, 0x00be, 0x00bf,
    }
    
    # Characters that are OK even at high frequency in text files
    SAFE_CHARS = set(range(0x2000, 0x2070)) | {0x2022, 0x2026, 0x2032, 0x2033, 0x25CF, 0x2605}

    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for f in sorted(files):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, repo_dir)
            
            ext = os.path.splitext(f)[1].lower()
            if ext in [".pyc", ".exe", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot"]:
                skipped += 1
                continue
            if f.startswith("."):
                skipped += 1
                continue
            
            with open(path, "rb") as fh:
                raw = fh.read()
            
            # 1. UTF-8 validity
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                issues.append((rel, "INVALID_UTF8", "Not valid UTF-8"))
                continue
            
            # 2. BOM check
            if raw[:3] == b"\xef\xbb\xbf":
                issues.append((rel, "BOM", "Has UTF-8 BOM"))
                continue
            
            # 3. Replacement characters
            count_repl = text.count("\ufffd")
            if count_repl > 0:
                issues.append((rel, "REPLACEMENT", f"{count_repl}x U+FFFD"))
                continue
            
            # 4. Mojibake detection via Unicode analysis
            non_ascii = [ord(c) for c in text if ord(c) > 127]
            
            if len(non_ascii) >= 5:
                # Count CJK characters
                cjk = sum(1 for cp in non_ascii if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF)
                # Count strong mojibake indicators
                moji = sum(1 for cp in non_ascii if cp in STRONG_MOJIBAKE)
                # Count safe chars
                safe = sum(1 for cp in non_ascii if cp in SAFE_CHARS)
                
                # If mojibake indicators exist AND there are very few CJK chars
                if moji > 0 and cjk == 0:
                    issues.append((rel, "MOJIBAKE", 
                        f"moji={moji} cjk={cjk} non-ascii={len(non_ascii)}"))
                    continue
            
            # 5. Garbled text: excessive "?" in short lines
            lines = text.split("\n")
            for i, line in enumerate(lines):
                s = line.strip()
                if not s or len(s) > 120:
                    continue
                if s.count("?") > 3:
                    issues.append((rel, "GARBLED", f"L{i+1}: {s[:60]}"))
                    break
            
            ok += 1
    
    # Print report
    print()
    print("=" * 60)
    print(f"  AUDIT: {repo_dir}")
    print(f"  OK: {ok} files  |  Issues: {len(issues)}  |  Skipped: {skipped}")
    print("=" * 60)
    
    if issues:
        print()
        print(f"  {'FILE':50s} {'TYPE':15s} DETAIL")
        print(f"  {'-'*48} {'-'*15} {'-'*40}")
        for rel, typ, detail in issues:
            print(f"  [!] {rel[:48]:48s} {typ:15s} {detail[:60]}")
        print()
        print(f"  >>> {len(issues)} issue(s) found. Fix before push. <<<")
    else:
        print()
        print(f"  >>> ALL CLEAN. Ready to push. <<<")
    
    return len(issues) == 0

def cmd_api(token, method, path, data=None):
    """Raw API call."""
    status, data = api_call(method, path, data=data, token=token)
    log(f"API {method} {path}: {status}")
    if data:
        log(json.dumps(data, indent=2, ensure_ascii=False)[:500])

# ─── MAIN ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GitHub Publish Automation")
    parser.add_argument("action", choices=["login", "push", "release", "topics", "api", "audit"],
                       help="Action to perform")
    parser.add_argument("--owner", default="diegin-skill", help="GitHub owner")
    parser.add_argument("--repo", default="diegin", help="Repository name")
    parser.add_argument("--dir", help="Repository directory (default: parent of scripts/)")
    parser.add_argument("--message", default="Update", help="Commit message")
    parser.add_argument("--tag", default="v1.0.0", help="Release tag")
    parser.add_argument("--name", help="Release name (default: same as tag)")
    parser.add_argument("--body", default="", help="Release body/notes")
    parser.add_argument("--prerelease", action="store_true", help="Mark as prerelease")
    parser.add_argument("--topics", nargs="+", help="Repository topics")
    parser.add_argument("--method", help="HTTP method for API call")
    parser.add_argument("--path", help="API path for API call")
    parser.add_argument("--data", help="JSON data for API call")
    
    args = parser.parse_args()
    
    if args.dir:
        REPO_DIR = os.path.abspath(args.dir)
    
    if args.action == "login":
        cmd_login()
    elif args.action == "push":
        cmd_push(args.owner, args.repo, args.message)
    elif args.action == "release":
        rname = args.name or args.tag
        cmd_release(args.owner, args.repo, args.tag, rname, args.body, args.prerelease)
    elif args.action == "topics":
        if args.topics:
            cmd_set_topics(args.owner, args.repo, args.topics)
        else:
            cmd_set_topics(args.owner, args.repo, 
                ["codex", "codex-skill", "ai-agent", "self-evolving", "dgen"])
    elif args.action == "audit":
        d = args.dir or REPO_DIR
        log(f"Auditing: {d}")
        clean = cmd_audit(d)
        sys.exit(0 if clean else 1)

    elif args.action == "api":
        token = read_token()
        if not token:
            raise RuntimeError("No token. Run login first.")
        data = json.loads(args.data) if args.data else None
        cmd_api(token, args.method, args.path, data)
