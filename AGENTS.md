# AGENTS.md - Aviastar n8n RAG AI Assistant

n8n workflow automation for Legal/HR RAG pipeline. Supabase pgvector + LLM.

**Implementations follow:** SDD, lean, DRY, non-breaking, 12-factor. Always research before coding.

## Research & Planning

- Research n8n node configs with `get_node` MCP tool before adding nodes.
- Reference n8n source at `..\n8n` for node implementations.
- Plan workflow changes before editing JSON — validate after each change.
- Deep web research for n8n docs: https://docs.n8n.io, GitHub issues.

## Engineering Baseline

- **Non-breaking:** Never break existing functionality. Test after each push.
- **Lean:** Remove dead nodes, unused connections, unnecessary complexity.
- **DRY:** Reuse patterns (embedding pipeline, metadata preparation).
- **SDD:** Spec-driven — the PDF spec at `references/docs/ТЗ_AI ассистент_HR_ЮрО.md` is the contract.
- **12-factor:** API keys in env vars, never in JSON/workflow. Backing services as attached resources.

## Dev Commands

```powershell
# Validate workflow JSON before pushing
# (uses n8n-mcp validate_workflow tool)

# Push to local n8n
python .agents/skills/n8n-workflow-sync/push.py

# Pull from local n8n
$env:N8N_WORKFLOW_ID="vonKtk32bMVn0Iw4"
python .agents/skills/n8n-workflow-sync/pull.py

# Verify n8n container
docker ps --filter "name=n8n"
docker logs n8n --tail 10
```

## Project Structure

- **`n8n/legal-rag.json`** — Main RAG workflow (source of truth, git-versioned)
- **`n8n/push.ps1`** — Deploy JSON to local n8n via REST API
- **`n8n/pull.ps1`** — Pull current state from n8n back to JSON
- **`sample-docs/`** — PDF documents for RAG indexing (mounted to n8n at `/docs`)
- **`references/`** — Reference workflows, AI research reports, URL bookmarks
- **`.agents/skills/`** — n8n skills for this repo

## Workflow Architecture

**Chat flow:** RAG Chatbot → Text Classifier (AI) → Gemini AI Agent → Supabase Vector Store → Confidence Check → Response

**Indexing flow:** Local Files (`/docs/*`) + Web (trudkod.ru) → Extract Text → Embeddings → Supabase Vector Store

**Key rules (from spec):**
- No answer without source or insufficient confidence (threshold: 0.6)
- No final legal docs through LLM without human verification
- LLM for search + answers; templates filled via code, not LLM
- Telegram bot with authorization (MVP phase 2)

## Security

- N8N_API_KEY in Windows user env var, never committed.
- Google Gemini API key in n8n credentials, not in workflow JSON.
- .gitignore excludes `.mcp.json`, `.env`, `*.log`, secrets.

## Commit Guidelines

- Only commit when explicitly asked.
- Keep messages concise: `"section: what changed"`.
- Generated message only — don't add/stage/push unless requested.

## n8n-Specific Notes

- Docker volume `n8n_data` persists workflows/credentials across container rebuilds.
- `docker volume rm n8n_data` = data loss. Never run without explicit user request.
- n8n v2.19.5 (stable tag = `docker.n8n.io/n8nio/n8n:latest`).
- API: `POST /api/v1/workflows` accepts `{name, nodes, connections, settings}`.
- Read/Write Files node looks relative to n8n container install path; use absolute paths.
- Text Classifier needs `ai_languageModel` connection to a model node.

## Two CLI Approaches

### Server CLI (Docker, no API key needed)
```powershell
# Export workflow to JSON
docker exec n8n n8n export:workflow --id=<ID> --output=/tmp/wf.json
docker cp n8n:/tmp/wf.json .\n8n\legal-rag.json

# Import workflow from JSON
docker cp .\n8n\legal-rag.json n8n:/tmp/wf.json
docker exec n8n n8n import:workflow --input=/tmp/wf.json

# Export all workflows + credentials (backup)
docker exec n8n n8n export:workflow --all --output=/tmp/backup.json
docker exec n8n n8n export:credentials --all --output=/tmp/creds.json
```
Server CLI runs inside the container, bypasses API auth, works even if API key is lost.

### Remote CLI (`@n8n/cli`, requires API key)
```powershell
# Install once
npm install -g @n8n/cli

# Configure
n8n-cli config set-url http://localhost:5678
n8n-cli config set-api-key $env:N8N_API_KEY

# CRUD operations
n8n-cli workflow list
n8n-cli workflow get <ID>
n8n-cli workflow create --stdin < workflow.json
n8n-cli workflow update <ID> --stdin < workflow.json
n8n-cli workflow delete <ID>
n8n-cli workflow activate <ID>
```
Remote CLI talks to n8n REST API, respects RBAC, in beta.

### REST API (our current approach)
```powershell
# Create workflow
Invoke-RestMethod -Uri "$N8N_URL/api/v1/workflows" -Method Post -Headers $headers -Body $body

# Get workflow
Invoke-RestMethod -Uri "$N8N_URL/api/v1/workflows/<ID>" -Headers $headers

# Update workflow
Invoke-RestMethod -Uri "$N8N_URL/api/v1/workflows/<ID>" -Method Put -Headers $headers -Body $body
```

## Reference Repositories

| Path | Content | Use |
|------|---------|-----|
| `..\n8n` | n8n source (TypeScript) | Node implementations, type structures |
| `..\n8n-docs` | n8n documentation (MDX) | Node docs, API docs, guides |
| `..\n8n-skills` | Claude Code skills for n8n | Skill reference, MCP usage patterns |
| `..\n8n-mcp` | n8n-mcp MCP server source | MCP tool behavior, env config, API client code |

## n8n CLI Quick Reference

```powershell
# Export (pull) — no API key needed
docker exec n8n n8n export:workflow --id=<ID> --output=/tmp/wf.json
docker cp n8n:/tmp/wf.json .\n8n\legal-rag.json

# Import (push, CREATE only — does NOT update existing)
docker cp .\n8n\legal-rag.json n8n:/tmp/wf.json
docker exec n8n n8n import:workflow --input=/tmp/wf.json

# For updates, use REST API (PUT) or push.py
```

## n8n Node Implementation Notes

### Chain LLM (`@n8n/n8n-nodes-langchain.chainLlm`) Parameters
- **typeVersion 1.3**: `prompt` (string, required) — simple text prompt
- **typeVersion 1.6**: `promptType` (options) + `text` field when promptType='define'
- Default prompt value: `={{ $json.chatInput }}` (v1.3) or `={{ $json.chat_input }}` (v1.1-1.2)
- Requires `ai_languageModel` connection

### Vector Store Tools: Scores Unavailable
- Both `ToolVectorStore` (legacy) and `retrieve-as-tool` (new) drop similarity scores from output
- `similaritySearchVectorWithScore` is called internally, but scores are discarded in formatting
- Confidence must come from: classifier confidence + LLM judge, not retrieval scores

### Reranker Availability
- `@n8n/n8n-nodes-langchain.rerankerCohere` — Cohere Rerank sub-node
- Connects via `ai_reranker` to vector store nodes
- Needs Cohere API key credential
- Improves retrieval precision but scores still not in tool output

## Critical: n8n UI Auto-Save Caveat

The n8n editor auto-saves nodes with only visible parameters — it strips fields that aren't shown in the current editor panel:
- Code node `mode: "runOnceForAllItems"` → stripped if not in the visible tab
- Structured Output Parser `schema` → stripped if schemaType panel is closed
- Chain LLM `options: {}` → stripped on resave

**Always pull + git diff after UI edits** to detect stripped parameters.

## Chain LLM Expression Caveat

Chain LLM `{{ $json.field }}` expressions resolve against the node's direct input data. If the upstream node doesn't forward a field (e.g., AI Agent output lacks `chatInput`), reference it from the source node:
```
{{ $('Enrich with Classification').first().json.chatInput }}
```
