<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# [https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger/](https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger/)

Will these work as as a starting point for the workflow?

Да, это очень хорошие стартовые точки — с оговоркой, что тебе их нужно **адаптировать под HR/юридическую доменную модель и Telegram вместо web‑чата**.

### Что у тебя уже есть и как это использовать

1. **`n8n-rag-tutorial.json` (Lucas Peyrin, Gemini + Supabase)**
    - Это полный учебный RAG‑workflow: наверху — индексатор (HTTP Request → Default Data Loader → Text Splitter → Supabase Vector Store `insert`), внизу — агент, который ходит в Supabase Vector Store как в tool и отвечает через Gemini, строго на основе документов.[^1][^2]
    - Это почти 1:1 то, что нужно по ТЗ:
        - RAG на Supabase Vector Store;
        - четко отделены ingestion и chat‑часть;
        - есть пример system prompt’а “отвечай только из документации”.[^1]
    - Что нужно изменить под твой кейс:
        - заменить источник документов (вместо `https://docs.n8n.io` — твой набор файлов/НПА);[^1]
        - сменить chunk размер на 500 и overlap 50 (сейчас там 1500/200);[^3][^1]
        - настроить таблицу `documents` в Supabase под нужные поля/метаданные (`file`, `section`, `date`);[^4][^1]
        - заменить `chatTrigger` и web‑чат на связку `Telegram Trigger` + `Telegram` node (см. ниже).
2. **Шаблон “Create a Documentation Expert Bot with RAG, Gemini, and Supabase” (workflow 5993)**
    - Это готовый туториал именно по RAG + Gemini + Supabase: сверху индексирование, снизу RAG‑chat, хранящий эмбеддинги в Supabase Vector Store.[^5][^2]
    - Отлично подходит как **референс структуры** и конфигурации Supabase credentials / vectorStoreSupabase узлов.[^2]
    - Для тебя это, по сути, эталон: как правильно связать Supabase Vector Store, Embeddings, Agent и Chat Trigger.
3. **Шаблон “AI Agent to chat with files in Supabase Storage” (workflow 2621)**
    - Этот workflow уже делает: загрузка файлов из Supabase Storage → обработка (в т.ч. PDF) → Text Splitter (по умолчанию как раз размер чанка 500) → OpenAI embeddings → Supabase Vector Store → chat‑агент, который отвечает по документам.[^6]
    - Это почти готовый blueprint под твой “чат с файлами компании”, нужно только:
        - переосмыслить схему файлов (какие bucket/table, какие метаданные — регламенты, политики, шаблоны);[^6]
        - заменить general‑chat интерфейс на Telegram (или использовать HTTP webhook + твой Telegram‑бот).[^6]
4. **Telegram Trigger docs**
    - `Telegram Trigger` — штатный нод, который ловит **новые сообщения, callback‑запросы** и т.п., и может ограничиваться по chat/user ID — удобно для белого списка.[^7]
    - `Telegram` app‑node умеет отправлять сообщения, редактировать их, отвечать на callback‑query inline‑клавиатуры (для “👍/👎” рейтинга ответа), отправлять документы и т.д.[^8][^9][^10]
    - То есть “фронт” ты строишь так:
        - `Telegram Trigger` → твой RAG/шаблонный workflow → `Telegram` → inline buttons;
        - отдельный workflow с `Telegram Trigger` на `Callback Query` для обработки оценки и логирования.[^10][^7]

### Вывод

- **Да**:
    - `n8n-rag-tutorial.json` + workflows 5993/2621 — это прямо “канонические” стартовые RAG‑шаблоны с Supabase, их можно импортировать и адаптировать под твой стэк и домен.[^2][^1][^6]
    - Документация по `Telegram Trigger` и `Telegram` node покрывает всё, что тебе нужно для Telegram‑фронтенда MVP (входящие сообщения, whitelist по ID, отправка ответов, inline‑клавиатуры, callback‑обработка).[^9][^8][^10][^7]
- Что нужно будет добавить руками к этим шаблонам под ТЗ:
    - сменить источник документов на HR/юридические и chunk‑параметры (500/50) + метаданные `file/section/date`;[^3][^1][^6]
    - заменить `chatTrigger`/web‑чат на Telegram Trigger + Telegram node;[^9][^7]
    - вставить блоки whitelist, logging (Supabase/Sheets), кнопки оценки и очередь bad answers;[^3][^6]
    - добавить поток генерации черновика по 1–2 шаблонам (через Code node или твой Python API) вместо “свободной” генерации договора.[^3]

То есть стратегически ты делаешь так: берешь один из этих RAG‑workflow как “ядро” (лучше 5993 или твой `n8n-rag-tutorial.json`), меняешь источники и параметры, а затем вокруг него навешиваешь Telegram‑слой, whitelist и логи.
<span style="display:none">[^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30][^31][^32][^33][^34][^35][^36][^37][^38][^39]</span>

<div align="center">⁂</div>

[^1]: n8n-rag-tutorial.json

[^2]: https://n8n.io/workflows/5993-create-a-documentation-expert-bot-with-rag-gemini-and-supabase/

[^3]: TZ_AI-assistent_HR_IurO.pdf

[^4]: https://www.linkedin.com/pulse/rag-agent-n8n-step-by-step-project-write-up-read-from-fazle-rabbi-trdqc

[^5]: https://n8n.io/workflows/5993-create-a-documentation-expert-bot-with-rag-gemini-and-supabase

[^6]: https://n8n.io/workflows/2621-ai-agent-to-chat-with-files-in-supabase-storage/

[^7]: https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger/

[^8]: https://n8n-docs.teamlab.info/integrations/builtin/app-nodes/n8n-nodes-base.telegram/

[^9]: https://www.n8nshow.com/en/docs/integrations/builtin/app-nodes/n8n-nodes-base.telegram

[^10]: https://n8n-docs.teamlab.info/integrations/builtin/app-nodes/n8n-nodes-base.telegram/callback-operations/

[^11]: claude-report-2.md

[^12]: gemini-report-3.md

[^13]: gpt-deep-research-report-01-4.md

[^14]: kimi-report-5.md

[^15]: AI-agent-to-chat-with-files-in-Supabase-Storage-n8n-workflow-template-6.url

[^16]: Community-edition-features-n8n-Docs-7.url

[^17]: Supabase-credentials-n8n-Docs-10.url

[^18]: self-hosted-ai-starter-kit-docker-compose.yml-at-main-n8n-io-self-hosted-ai-starter-kit-9.url

[^19]: Telegram-Trigger-node-documentation-n8n-Docs-14.url

[^20]: Create-a-Documentation-Expert-Bot-with-RAG-Gemini-and-Supabase-n8n-workflow-template-15.url

[^21]: https://github.com/diegoperea20/n8n-rag-gemini-supabase

[^22]: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/

[^23]: https://www.youtube.com/watch?v=xzUb6ER5FkY

[^24]: https://www.youtube.com/watch?v=jakZIZe776Y

[^25]: https://n8n.io/workflows/6137-build-a-documentation-expert-chatbot-with-gemini-rag-pipeline/

[^26]: https://www.youtube.com/watch?v=hIdqAi_vvEs

[^27]: https://www.reddit.com/r/n8n/comments/1mh1rm3/i_built_a_complete_ai_chatbot_rag_system_using/

[^28]: https://www.youtube.com/watch?v=d8kVgOv9FVE

[^29]: https://n8nautomation.cloud/workflows/ai-agent-to-chat-with-files-in-supabase-storage

[^30]: https://n8n.io/integrations/supabase/

[^31]: https://github.com/nusquama/n8nworkflows.xyz?via=ailibricom

[^32]: https://n8n.io/workflows/4086-ai-agent-to-chat-with-files-in-supabase-storage-and-google-drive/

[^33]: https://www.reddit.com/r/n8n/comments/1hbb5l9/ai_agent_to_chat_with_files_in_supabase_storage/

[^34]: https://www.youtube.com/watch?v=P1-t_6-EYK0

[^35]: https://www.youtube.com/watch?v=glWUkdZe_3w

[^36]: https://n8n.io/workflows/2612-ai-agent-to-chat-with-supabasepostgresql-db/

[^37]: https://www.youtube.com/watch?v=YR30uzwWoDM

[^38]: https://hackceleration.com/supabase-n8n/

[^39]: https://n8n-library.com/workflow/ai-agent-to-chat-with-files-in-supabase-storage/

