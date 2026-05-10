PHASE 1 — Подготовка документов  - переделай под n8n: GoogleDrive/Docs + HTML webfetch n8n node. Chunking too with n8n as in first-MVP.json

For GoogleDrive/Docsand Telegram take ideas from Nutrition-tracker-meal-logger-with-Telegram,-Gemini-AI-and-Google-Sheets.json and 2395-supabase-insertion-and-upsertion-and-retrieval.json



Both workflows validate cleanly. Here's exactly what to do with them.

---

## Import & configure

In n8n: **Menu → Workflows → Import from file** — import each JSON separately. They become two independent workflows you run once per indexing session.

---

## Workflow 01a — Google Drive PDFs

**Flow:** `▶ Start` → `📋 File List` → `Split Files` → `🔁 Loop` → `Google Drive Download` → `📎 Prepare Metadata` → `📥 Insert to Supabase` (← sub-nodes: PDF Loader + Text Splitter + Embeddings) → loops back → `✅ Done`

### What to configure

**1. `📋 File List (edit me)` node** — this is the only node you edit manually. Replace each `"PASTE_GOOGLE_DRIVE_FILE_ID_HERE"` with actual IDs:

```
https://drive.google.com/file/d/  ← FILE_ID IS HERE  /view
                                    ^^^^^^^^^^^^^^^^
```

Edit the `name`, `section`, and `date` fields to match your documents. Add or remove entries freely — it's just a JSON array.

**2. Google Drive credential** — connect your Google account in the `Google Drive Download` node (n8n credential → Google OAuth2).

**3. `📥 Insert to Supabase`** — should auto-use your existing Supabase credential from first-MVP.json. Table name is `documents` (matches Phase 0 schema).

**4. `🔢 OpenAI Embeddings`** — uses `text-embedding-3-small` (1536 dims). Must match the vector size in your Supabase table.

### Important: SplitInBatches output port mapping

The loop uses the **same port assignment as first-MVP.json**: `output[1]` = current batch items, `output[0]` = done. This matches the observed n8n behavior in your working prototype. If after import the loop doesn't fire the download step, swap the connections on the loop node's outputs in the GUI.

### What the `📎 Prepare Metadata` Code node does

```javascript
// Reads the file list metadata (name/section/date) from the loop context
// since Google Drive Download replaces the item's JSON with binary data.
// Passes both the binary PDF AND the metadata JSON fields forward
// so the Default Data Loader can read both.
const file = $('🔁 Loop Over Files').first().json.file;
return [{ json: { file_name, file_section, file_date }, binary: $input.first().binary }];
```

The `📄 PDF Loader + Metadata` sub-node then reads `$json.file_name` etc. via the metadata options to stamp each chunk with `{file, section, date}` in Supabase's `metadata` JSONB column.

### Chunk size rationale

`chunkSize: 1200, chunkOverlap: 120` approximates the TZ's `TokenTextSplitter(500, 50)`:
- Russian Cyrillic in `cl100k_base`: ~2–2.5 chars per token
- 1200 chars ÷ 2.4 ≈ 500 tokens ✓
- 120 chars ÷ 2.4 ≈ 50 tokens overlap ✓

For the demo this is fine. If the interviewer asks, note it's a character-based approximation and exact token counting requires `tiktoken` via a Python Code node.

---

## Workflow 01b — Web URL HTML Fetch

**Flow:** `▶ Start` → `🌐 URL List` → `Dedup` → `🔁 Loop` → `🌍 Fetch Page HTML` → `📰 Extract Main Content` → `🧹 Clean Text + Metadata` → `Skip Already Indexed` → `📥 Insert to Supabase` → loops back

### What to configure

**1. `🌐 URL List` Code node** — edit the `urls` array at the top. Five legal URLs are pre-seeded. Add your external source:

```javascript
{
  url:     "https://your-legal-source.ru/page",
  name:    "Название документа",
  section: "Категория",
  date:    "2024-01-01"
}
```

**2. `📰 Extract Main Content` HTML node** — the CSS selector `article, main, .content, .document, #content, .article, p` works for most Russian legal sites. If a particular site returns empty content, open DevTools on that page, find the main content wrapper's class/id, and add it to the selector list.

**3. `Skip Already Indexed` node** — uses `removeItemsSeenInPreviousExecutions` on `source_url`. This means re-running the workflow won't re-index pages that were already processed. To force a full re-index, go into the node and clear its deduplication history.

### Likely issues with specific sites

| Site | Likely CSS selector | Notes |
|---|---|---|
| consultant.ru | `.document`, `#article` | May require cookies/JS — use a cached/mirror if blocked |
| онлайнинспекция.рф | `main`, `.questions` | Usually clean HTML |
| mintrud.gov.ru | `main`, `.text-page` | Good structure |

If a site blocks the default User-Agent or requires JS rendering, use a cached version from `docs.cntd.ru` or `base.garant.ru` which serve static HTML.

---

## ✅ Phase 1 checkpoint after running both

```sql
-- Should show your indexed sources
SELECT 
  metadata->>'file'    AS document,
  metadata->>'section' AS section,
  metadata->>'source'  AS source,
  COUNT(*)             AS chunks
FROM documents
GROUP BY 1, 2, 3
ORDER BY chunks DESC;
```

Expected: 5–15 rows, 100–600 total chunks depending on document sizes. Each chunk will have `{file, section, date, source}` in its metadata, ready for the confidence-scored retrieval in Phase 3.
