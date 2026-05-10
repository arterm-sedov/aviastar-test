# n8n-mcp Management Tools Not Registering: Research Findings

## Research Date: 2026-05-11

---

## 1. Why Management Tools Don't Show Up When N8N_API_URL and N8N_API_KEY Are Set

### Root Cause: Conditional Tool Registration

From source code analysis (`src/mcp/server.ts`), management tools are **conditionally registered** in the `ListToolsRequestSchema` handler:

```typescript
const hasEnvConfig = isN8nApiConfigured();
const hasInstanceConfig = !!(this.instanceContext?.n8nApiUrl && this.instanceContext?.n8nApiKey);
const isMultiTenantEnabled = process.env.ENABLE_MULTI_TENANT === 'true';
const shouldIncludeManagementTools = hasEnvConfig || hasInstanceConfig || isMultiTenantEnabled;
```

The `isN8nApiConfigured()` function from `src/config/n8n-api.ts` uses **Zod validation**:

```typescript
const n8nApiConfigSchema = z.object({
  N8N_API_URL: z.string().url().optional(),  // MUST be valid URL!
  N8N_API_KEY: z.string().min(1).optional(),  // MUST be non-empty!
});
```

**`N8N_API_URL` must satisfy `z.string().url()`** — if it's not a valid URL format, `safeParse` fails and the config returns `null`, causing management tools to be excluded.

### Common Failure Modes:

1. **URL is not a valid URL format** — eg missing protocol, invalid characters
2. **Environment variables not reaching the process** — especially on Windows with npx/Claude Desktop (#627)
3. **`DISABLED_TOOLS` env var explicitly filtering management tools**

**Source**: https://github.com/czlonkowski/n8n-mcp/blob/main/src/mcp/server.ts
**Source**: https://github.com/czlonkowski/n8n-mcp/blob/main/src/config/n8n-api.ts

---

## 2. Special Configuration Requirements

### URL Format Requirements:

From `.env.example`:
```
# n8n instance API URL (without /api/v1 suffix)
# Example: https://your-n8n-instance.com
# N8N_API_URL=
```

**Critical**: `N8N_API_URL` must NOT include `/api/v1`. The API client appends it automatically:
```typescript
const apiUrl = normalizedBase.endsWith('/api/v1')
  ? normalizedBase
  : `${normalizedBase}/api/v1`;
```

If you set `N8N_API_URL=https://your-instance.com/api/v1`, it becomes `https://your-instance.com/api/v1/api/v1` — double-prefixed and broken.

### Windows-Specific Issue (#627):

On Windows with Claude Desktop + `npx`, environment variables in `claude_desktop_config.json` may NOT be passed to the npx process. This manifests as:
- n8n API showing "not configured" 
- Management tools not listed in `tools/list`
- All documentation tools working fine

This issue was **closed** but there may still be residual problems with certain Claude Desktop versions.

**Source**: https://github.com/czlonkowski/n8n-mcp/issues/627 (Closed)

### URL Rewriting Bug (#594):

In v2.35.2, there was a bug where the base URL gets rewritten to append `/mcp-server/http`:
- User sets: `N8N_API_URL=https://instance.hstgr.cloud`
- Internally becomes: `https://instance.hstgr.cloud/mcp-server/http`
- API calls become: `https://instance.hstgr.cloud/mcp-server/http/api/v1/workflows` → 404

This was particularly problematic for instances that expose a `/mcp-server/http` endpoint (native n8n MCP Server Trigger).

**Source**: https://github.com/czlonkowski/n8n-mcp/issues/594 (Closed)
**Related**: https://github.com/czlonkowski/n8n-mcp/issues/736 (Closed)

### SSRF Protection:

When `N8N_API_URL` points to localhost (e.g., `http://localhost:5678`), set `WEBHOOK_SECURITY_MODE=moderate`. The default `strict` mode blocks loopback addresses for both webhook triggers and the API client.

**Source**: https://github.com/czlonkowski/n8n-mcp/blob/main/docs/SELF_HOSTING.md

---

## 3. n8n-mcp v2.51.1 and n8n v2.19.5 Compatibility

### Known n8n Version Contract Issues:

**Issue #737** reports that n8n-mcp 2.12.2 had serious schema contract mismatches with n8n 2.16.0:
- `update_full_workflow`: `TypeError: Cannot read properties of undefined (reading '_zod')`
- `update_partial_workflow`: `400 VALIDATION_ERROR: request/body must NOT have additional properties`
- n8n 2.16.0 enforces `additionalProperties: false` on `settings`

Read-only tools (`get_workflow`, `list_workflows`, `health_check`, `list_executions`, `validate_*`) worked fine.

**Source**: https://github.com/czlonkowski/n8n-mcp/issues/737 (Closed)

### Version Compatibility Gap:

v2.51.1 is the latest (May 6, 2026), while v2.12.2 tested against n8n 2.16.0. There is a significant version gap. Testing against n8n 2.19.5 is advised — while not known to have specific issues, the schema contract mismatch pattern could resurface.

**Issue #549** specifically requests documentation on version compatibility between n8n-mcp and n8n instances. This is still open, indicating no comprehensive compatibility matrix exists.

**Source**: https://github.com/czlonkowski/n8n-mcp/issues/549 (Open)
**Source**: https://github.com/czlonkowski/n8n-mcp/issues/737 (Closed)

---

## 4. N8N_API_URL Format Requirements

### Exact Expected Format:

```
https://your-instance.com          ← CORRECT
https://your-instance.com:5678     ← CORRECT (with port)
http://localhost:5678              ← CORRECT (local dev)

https://your-instance.com/api/v1   ← WRONG (don't include /api/v1)
https://your-instance.com/         ← WRONG (no trailing slash)
your-instance.com                  ← WRONG (must include protocol)
```

### Verification:

From `.env.example`:
```
# n8n instance API URL (without /api/v1 suffix)
# Example: https://your-n8n-instance.com
```

From `n8n-api-client.ts`:
```typescript
// Ensure baseUrl ends with /api/v1
const apiUrl = normalizedBase.endsWith('/api/v1')
  ? normalizedBase
  : `${normalizedBase}/api/v1`;
```

The client normalizes: strips trailing slash, appends `/api/v1`. It does NOT strip an existing `/api/v1` suffix — instead it double-appends.

### URL Validation:

Zod's `.url()` validation requires a valid URL with protocol. The config will be rejected if:
- Missing protocol (`http://` or `https://`)
- Invalid URL characters
- Empty string

---

## 5. GitHub Issues About Management Tools Not Appearing

### Key Issues Found:

| Issue | Title | Status | Relevance |
|-------|-------|--------|-----------|
| [#627](https://github.com/czlonkowski/n8n-mcp/issues/627) | Windows: env variables not passed to npx process — n8n API shows as "not configured" | Closed | **HIGHLY RELEVANT** - Same symptom on Windows |
| [#6](https://github.com/czlonkowski/n8n-mcp/issues/6) | Tool Count Discrepancy: Diagnostic Reports 38 Tools but MCP tools/list Only Returns 22 | Closed | Original issue about management tools not in tools/list |
| [#594](https://github.com/czlonkowski/n8n-mcp/issues/594) | Management tools return 404 or HTML despite correct N8N_API_URL | Closed | URL rewriting bug |
| [#736](https://github.com/czlonkowski/n8n-mcp/issues/736) | n8n_audit_instance fails with "Invalid URL" | Closed | URL construction issues |
| [#78](https://github.com/czlonkowski/n8n-mcp/issues/78) | Remote connection to N8N instance using n8n-remote failed | Open | Remote connection issues |
| [#737](https://github.com/czlonkowski/n8n-mcp/issues/737) | update_full_workflow broken on n8n 2.16.0 | Closed | Schema contract mismatch with newer n8n |
| [#549](https://github.com/czlonkowski/n8n-mcp/issues/549) | Request: Version compatibility documentation | Open | No compatibility matrix exists |
| [#627](https://github.com/czlonkowski/n8n-mcp/issues/627) | env variables not passed to npx process | Closed | Windows + Claude Desktop specific |

### All Issue URLs:
- https://github.com/czlonkowski/n8n-mcp/issues/627
- https://github.com/czlonkowski/n8n-mcp/issues/594
- https://github.com/czlonkowski/n8n-mcp/issues/736
- https://github.com/czlonkowski/n8n-mcp/issues/737
- https://github.com/czlonkowski/n8n-mcp/issues/6
- https://github.com/czlonkowski/n8n-mcp/issues/78
- https://github.com/czlonkowski/n8n-mcp/issues/549

---

## 6. Tool Registration and API Health Check Dependency

### Key Finding: NO startup API health check required

Management tool registration does NOT depend on a successful API health check on startup. The registration is purely based on:

1. Environment variables (`N8N_API_URL` and `N8N_API_KEY` being set and valid)
2. Instance context (for multi-tenant mode)
3. `ENABLE_MULTI_TENANT` flag

From `server.ts`:
```typescript
this.initialized = this.initializeDatabase(dbPath).then(() => {
  if (this.earlyLogger) {
    this.earlyLogger.logCheckpoint(STARTUP_CHECKPOINTS.N8N_API_CHECKING);
  }
  const apiConfigured = isN8nApiConfigured();
  const totalTools = apiConfigured ?
    n8nDocumentationToolsFinal.length + n8nManagementTools.length :
    n8nDocumentationToolsFinal.length;
  logger.info(`MCP server initialized with ${totalTools} tools (n8n API: ${apiConfigured ? 'configured' : 'not configured'})`);
  if (this.earlyLogger) {
    this.earlyLogger.logCheckpoint(STARTUP_CHECKPOINTS.N8N_API_READY);
  }
});
```

The `n8n_health_check` tool performs a runtime check (tries `/healthz` endpoint, falls back to listing workflows), but this is only called when the tool is explicitly invoked, not during registration.

**The health check can produce false positives**: In issue #594, `health_check` reported `connected: true` but actual management API calls failed with 404 because the base URL had been rewritten to include `/mcp-server/http`.

---

## Summary of Recommendations

1. **Verify URL format**: `N8N_API_URL` must be `https://your-instance.com` (no `/api/v1`, no trailing slash, must have protocol)
2. **On Windows**: Try using absolute `node` path instead of `npx` in MCP config, or use Docker deployment
3. **Check logs**: Look for "n8n API: not configured" in startup logs — this means env vars aren't reaching the process
4. **Call `n8n_health_check`** after setup to verify connectivity — but be aware it can be a false positive
5. **Test with curl first** to confirm the n8n instance API is accessible with the provided URL and key
6. **Check Zod validation**: If `N8N_API_URL` fails the `.url()` validation, management tools won't register even if the URL "works" in a browser
