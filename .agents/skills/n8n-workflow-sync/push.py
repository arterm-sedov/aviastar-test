"""Push n8n workflow JSON to n8n via REST API (reads keys from process env or Windows registry)."""
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
WF_PATH = os.environ.get("N8N_WORKFLOW_PATH",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "n8n", "legal-rag.json")))
WF_ID = os.environ.get("N8N_WORKFLOW_ID", "")

if not N8N_KEY:
    print("ERROR: N8N_API_KEY not set in environment", file=sys.stderr)
    sys.exit(1)

with open(WF_PATH, encoding="utf-8-sig") as f:
    wf = json.load(f)

body = json.dumps({
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {"executionOrder": "v1"}
}).encode()

url = f"{N8N_URL}/api/v1/workflows"
method = "POST"
if WF_ID:
    url = f"{url}/{WF_ID}"
    method = "PUT"
    print(f"Updating workflow {WF_ID}...")
else:
    print(f"Creating '{wf['name']}'...")

req = urllib.request.Request(url, data=body, method=method)
req.add_header("X-N8N-API-KEY", N8N_KEY)
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(f"Done: {result['id']} - {result['name']}")
        if not WF_ID:
            print(f"Set N8N_WORKFLOW_ID={result['id']} for future pushes")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
