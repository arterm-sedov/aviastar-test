"""Pull n8n workflow JSON via REST API (reads keys from process env or Windows registry)."""
import json, os, sys, urllib.request, urllib.error

def _env(key, default=None):
    for src in [os.environ.get(key), _from_winreg(key)]:
        if src: return src
    return default

def _from_winreg(key):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, key)[0]
    except Exception:
        return None

N8N_URL = _env("N8N_API_URL", "http://localhost:5678")
N8N_KEY = _env("N8N_API_KEY")
WF_ID = _env("N8N_WORKFLOW_ID", "")
OUTPUT = os.environ.get("N8N_WORKFLOW_PATH",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "n8n", "legal-rag.json")))

if not N8N_KEY:
    print("ERROR: N8N_API_KEY not set in environment", file=sys.stderr)
    sys.exit(1)
if not WF_ID:
    print("ERROR: N8N_WORKFLOW_ID not set in environment", file=sys.stderr)
    print("  Set N8N_WORKFLOW_ID=<id> or pass --id <id>", file=sys.stderr)
    sys.exit(1)

req = urllib.request.Request(f"{N8N_URL}/api/v1/workflows/{WF_ID}")
req.add_header("X-N8N-API-KEY", N8N_KEY)

try:
    with urllib.request.urlopen(req) as resp:
        wf = json.loads(resp.read())
        for key in ("id", "versionId", "createdAt", "updatedAt", "shared"):
            wf.pop(key, None)
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        print(f"Pulled: {wf['name']} -> {OUTPUT} (nodes={len(wf['nodes'])}, active={wf.get('active')})")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
