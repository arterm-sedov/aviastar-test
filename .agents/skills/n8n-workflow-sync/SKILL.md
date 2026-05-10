---
name: n8n Workflow Sync
description: Push and pull n8n workflows between local JSON files and a running n8n instance. Use when the user asks to push, pull, sync, deploy, export, import, or update an n8n workflow. Triggers: "push workflow", "pull workflow", "sync n8n", "deploy workflow", "export n8n", "import n8n", "update n8n instance".
---

# n8n Workflow Sync

Push and pull n8n workflows between local JSON files and a running n8n instance via REST API.

## Prerequisites

- `N8N_API_KEY` environment variable (Windows user env or `$env:` in PS)
- `N8N_API_URL` defaults to `http://localhost:5678`
- Python 3 (stdlib only, no dependencies)

## Scripts

### push.py

Push `n8n/legal-rag.json` to n8n instance.

```powershell
$env:N8N_API_KEY="<key>"
python .agents/skills/n8n-workflow-sync/push.py
```

Set `N8N_WORKFLOW_ID` env var to update an existing workflow instead of creating new.

```powershell
$env:N8N_WORKFLOW_ID="vonKtk32bMVn0Iw4"
python .agents/skills/n8n-workflow-sync/push.py
```

### pull.py

Pull a workflow from n8n and save to `n8n/legal-rag.json`.

```powershell
$env:N8N_API_KEY="<key>"
$env:N8N_WORKFLOW_ID="vonKtk32bMVn0Iw4"
python .agents/skills/n8n-workflow-sync/pull.py
```

## Env Vars

| Var | Default | Description |
|-----|---------|-------------|
| `N8N_API_KEY` | required | n8n API key |
| `N8N_API_URL` | `http://localhost:5678` | n8n instance URL |
| `N8N_WORKFLOW_ID` | push: new; pull: required | Workflow ID |
| `N8N_WORKFLOW_PATH` | `n8n/legal-rag.json` | Local JSON path |
