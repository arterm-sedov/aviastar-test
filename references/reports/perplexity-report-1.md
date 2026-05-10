<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Диаграму они хотят в нотации [https://swimlanes.io/](https://swimlanes.io/), похоже там Sequence Diagram

[https://swimlanes.io/gallery/full-syntax](https://swimlanes.io/gallery/full-syntax)

И подскажи по узлам в n8n подробнее, какие готовые узлы использовать, поищи в нитрентене

Подробнее опиши что с телеграмой, есть ли готовая в n8n поддержка

Мне нужно это всё мышью настраивать или claude code, codex, opencode, cursor могут мне сделать n8n и workflow в нём через JSON?

Да, у **swimlanes.io** основной синтаксис ближе к textual sequence/swimlane notation, а не к BPMN 2.0 XML; для твоего задания это удобно, потому что можно быстро нарисовать процесс по дорожкам как взаимодействие ролей и систем.  Для MVP это даже лучше классического BPMN-редактора: покажешь lanes, сообщения, развилки и notes, не тратя время на тяжелое моделирование.[^1]

## Swimlanes.io

В твоем случае делай не “чистую BPMN-диаграмму”, а **swimlane sequence diagram** с дорожками: `Сотрудник`, `Telegram Bot`, `n8n`, `Supabase/KB`, `HR/Legal Reviewer`.  Это хорошо покрывает пользовательский запрос, авторизацию, retrieval, confidence-gate, ответ с источниками, feedback и review queue — именно те шаги, которые требуются в ТЗ.[^2][^1]

Пример структуры для swimlanes.io:

```text
title: AI assistant MVP for HR / Legal

Employee -> Telegram Bot: Send question
Telegram Bot -> n8n: Forward message + user_id
n8n -> n8n: Check whitelist
alt authorized
  n8n -> n8n: Classify request
  alt knowledge question
    n8n -> Supabase/KB: Retrieve chunks
    Supabase/KB --> n8n: Top-k chunks + metadata
    n8n -> n8n: Check confidence / source sufficiency
    alt enough evidence
      n8n --> Telegram Bot: Answer with citations
      Telegram Bot --> Employee: Send answer + rating buttons
    else low confidence
      n8n --> Telegram Bot: Safe refusal / ask to contact expert
      Telegram Bot --> Employee: Send refusal
    end
  else draft request
    n8n -> Supabase/KB: Get template + reference data
    Supabase/KB --> n8n: Template / fields
    n8n -> n8n: Fill template fields by code
    n8n --> Telegram Bot: Draft for review
    Telegram Bot --> Employee: Send draft with disclaimer
  end
  Employee -> Telegram Bot: Rate answer
  Telegram Bot -> n8n: Feedback callback
  n8n -> Supabase/KB: Save logs + feedback
  alt negative feedback
    n8n -> HR/Legal Reviewer: Put into review queue
  end
else unauthorized
  n8n --> Telegram Bot: Access denied
  Telegram Bot --> Employee: Access denied
end
```

Такую диаграмму можно прямо вставить в редактор swimlanes.io и потом руками немного причесать. Смысловой плюс в том, что она показывает **межсистемное взаимодействие**, а не только статическую схему процесса.[^1][^2]

## Узлы n8n

Для твоего кейса в n8n уже есть готовые узлы под Telegram и RAG, так что “с нуля кодить всё” не надо. У n8n есть встроенные Telegram Trigger и Telegram app node, а для RAG есть документация по vector store, embeddings, loaders и query flow.[^3][^4][^5][^6]

Ниже — практический набор узлов для MVP.

### 1. Вход из Telegram

- **Telegram Trigger** — принимает входящие сообщения, callback query и другие события.[^4][^2]
- **Switch** — ветвление по типу события: текстовый вопрос, callback от кнопки, команда `/start`.
- **IF** — whitelist check по `user_id`, если нужно простое условие.
- **Set** — нормализовать поля, например `user_id`, `chat_id`, `text`, `intent`.

`Telegram Trigger` умеет ограничивать workflow по chat IDs и user IDs, что полезно для MVP-белого списка даже без отдельной БД.[^3][^2]

### 2. Классификация и роутинг

- **OpenAI Chat Model** или другой LLM node — классификация запроса: `hr_question`, `legal_question`, `draft_request`, `out_of_scope`.
- **Structured Output Parser** или просто строгий JSON-ответ через prompt.
- **Switch** — маршрутизация по intent.
- **Code** node — если хочешь жестко нормализовать JSON, score, citations.

Это один из тех участков, где n8n удобно сочетать с кодом: routing мышкой, а валидацию структуры ответа — коротким JS/Python-кодом.

### 3. Индексация документов

Для ingestion-пайплайна удобно использовать:

- **Manual Trigger** или **Cron** — запуск индексации.
- **Read/Load file** источника, либо **HTTP Request** если грузишь внешний документ/страницу.
- **Default Data Loader** — подготовка документа к chunking.[^5]
- **Token Text Splitter** — под твое ТЗ на чанки 500 токенов и overlap 50.[^5][^2]
- **Embeddings node** — модель эмбеддингов.
- **Supabase Vector Store** с операцией **Insert Documents** — запись чанков в pgvector.[^6]

n8n прямо рекомендует для RAG использовать Data Loader + Text Splitter + Vector Store с embedding model, а metadata можно прикреплять к chunk’ам для последующей фильтрации.  Это почти один-в-один совпадает с ТЗ: `file`, `section`, `date`, chunk size 500, overlap 50.[^6][^2][^5]

### 4. Retrieval и ответ

Есть два рабочих варианта.

**Вариант A — “по-нэйтивному в n8n”:**

- **Embeddings / Agent flow**
- **Supabase Vector Store** с retrieval/query
- **Vector Store Question Answer Tool** или agent+tool pattern
- **Chat Model**
- **Code / IF** для confidence gating

**Вариант B — “контролируемый MVP”:**

- n8n вызывает твой Python API через **HTTP Request**
- Python делает retrieval / rerank / score
- n8n только отправляет результат в Telegram и пишет логи

Для интервью я бы выбрал гибрид: ingestion и orchestration в n8n, а retrieval scoring можно вынести в Python, если тебе так надежнее. Это не нарушает ТЗ, потому что обязательны n8n и RAG, но не сказано, что весь пайплайн должен жить только внутри узлов.[^2]

### 5. Логирование и feedback

- **Telegram** node для отправки ответа.
- **Telegram Trigger** на `Callback Query` для нажатий кнопок.[^7][^4]
- **Supabase** или **Google Sheets** node / HTTP Request — запись логов и оценок.[^3]
- **IF** — если feedback negative, класть в review queue.
- **Send Message** / **Edit Message Text** — можно подтверждать принятие feedback.[^3]

ТЗ прямо просит логировать все запросы, собирать оценки и плохие ответы отправлять в очередь review.  Это в n8n легко делается отдельным workflow `save_feedback`, который ловит callback data вроде `good`, `bad`, `needs_review`.[^3]

## Telegram в n8n

Да, **готовая поддержка Telegram в n8n есть**. Для приема входящих событий используется `Telegram Trigger`, а для отправки/редактирования сообщений — обычный `Telegram` node.[^4][^3]

Что он умеет для твоего MVP:

- принимать новые сообщения через `Message` event;[^4]
- принимать `Callback Query`, что как раз подходит для кнопок “полезно / не полезно”;[^7][^4]
- ограничивать обработку по chat IDs и user IDs;[^4]
- отправлять сообщения, документы, индикатор typing/action, редактировать сообщения;[^3]
- работать с файлами, если позже захочешь загрузку документов через Telegram.[^3]

Для MVP Telegram-бота тебе обычно нужны всего 3 сущности:

1. **BotFather** — создать бота и получить token.
2. **Telegram credentials в n8n** — хранить токен, не в коде.[^2][^3]
3. **Webhook/Trigger workflow** — `Telegram Trigger` на события `Message` и `Callback Query`.[^4]

По безопасности: в ТЗ у тебя есть whitelist и требование хранить ключи в env, не в коде.  Для демо можно сделать двухуровневую проверку:[^2]

- первичная — в самом `Telegram Trigger` через restrict user/chat IDs, если подходит;[^4]
- вторичная — через `IF` или `Code` node, сравнивая `user_id` с env-переменной/списком.


## Кнопки в Telegram

Для оценки ответа тебе нужны **inline keyboard buttons**, а потом обработка `Callback Query`. n8n поддерживает callback operations и trigger на callback queries, так что сценарий “показал ответ → пользователь нажал кнопку → сохранили рейтинг” реализуем готовыми узлами.[^7][^4]

Типовой сценарий такой:

- `Telegram` node отправляет ответ и inline keyboard:
    - “👍 Полезно”
    - “👎 Не помогло”
    - “📌 На ревью”
- `Telegram Trigger` ловит `Callback Query`.[^4]
- `Switch` разбирает `callback_data`.
- `Supabase/Sheets` пишет feedback.
- При `bad` — отдельная запись в review queue.[^3]

Это один из самых убедительных элементов демо, потому что показывает не только Q\&A, но и цикл улучшения качества.[^3]

## Нужно ли всё мышью

Нет, **не только мышью**. n8n — визуальный редактор, но workflow хранится как JSON, и его можно импортировать в UI из файла или по URL.  Это значит, что Claude Code, Codex, Cursor, OpenCode и другие агенты вполне могут помочь тебе **сгенерировать skeleton workflow в JSON**, который потом импортируется и донастраивается в редакторе.[^8]

Но тут есть важная практическая оговорка:

- AI хорошо генерирует **каркас** workflow JSON.
- AI средне справляется с точными credential bindings, ID узлов, expression references и version-specific параметрами.
- Поэтому лучший режим — **генерация 60–80%**, потом ручная правка в UI.

То есть реальный процесс обычно такой:

1. Ты руками собираешь минимальный workflow в UI.
2. Экспортируешь JSON.[^8]
3. Даешь этот JSON Claude/Codex/Cursor как образец.
4. Просишь расширить его: добавить Switch/IF/Code/Telegram steps.
5. Импортируешь обратно.[^8]

Так надежнее, чем просить модель “с нуля напиши идеальный n8n workflow JSON”, потому что у n8n довольно чувствительная структура экспорта и мелкие несовпадения ломают импорт или поведение.

## Что лучше тебе лично

С учетом того, что ты привык к Python, а n8n для тебя новый, я бы рекомендовал такой режим работы:

- **Мышью** собрать:
    - Telegram Trigger
    - IF whitelist
    - Switch по intent
    - Telegram Send Message
    - basic logging
- **Кодом/AI** сделать:
    - prompts для классификации,
    - Code node snippets,
    - JSON skeleton для ingestion/retrieval,
    - Python helper service для template filling и, если надо, retrieval scoring.

Это даст хороший баланс: визуально ты понимаешь процесс и можешь показать его на интервью, а сложную рутину снимаешь код-ассистентами.

## Практический стек узлов

Для MVP я бы предложил такой минимальный конструктор.

### Workflow 1: `tg_entrypoint`

- Telegram Trigger
- Set
- IF whitelist
- Switch command/type
- LLM classify
- Switch intent
- Execute subworkflow / call HTTP


### Workflow 2: `rag_answer`

- Set normalized query
- Embeddings / Chat model
- Supabase Vector Store `Get Many` or retrieval tool[^6]
- Code node: score threshold / citations formatting
- IF enough evidence
- Telegram Send Message
- Supabase log row


### Workflow 3: `draft_generator`

- Telegram Trigger or Execute Workflow
- Set extracted fields
- Code / HTTP Request to Python template service
- Telegram Send Message
- Supabase log row


### Workflow 4: `feedback_handler`

- Telegram Trigger on Callback Query[^4]
- Switch callback value
- Supabase / Sheets insert
- IF negative → review queue


### Workflow 5: `document_ingest`

- Manual Trigger / Cron
- HTTP Request / file loader
- Default Data Loader[^5]
- Token Text Splitter[^5]
- Embeddings model[^5]
- Supabase Vector Store `Insert Documents`[^6]


## Что сказать на встрече

Сильная формулировка будет такой: n8n позволяет собрать MVP mostly low-code, Telegram поддерживается штатно, а workflow можно как собирать мышью, так и импортировать из JSON, поэтому разработка ускоряется за счет AI-assisted generation, но критические места — credentials, triggers, expressions и threshold logic — я валидирую вручную в UI.[^8][^4][^3]

Если хочешь, следующим сообщением я могу дать тебе уже **готовый текст для swimlanes.io**,
**список конкретных узлов n8n по каждому workflow**,
и **черновой JSON-скелет структуры n8n workflow**, чтобы ты быстрее стартовал.
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^9]</span>

<div align="center">⁂</div>

[^1]: https://github.com/drhoffmann/docsify-swimlanes-io

[^2]: TZ_AI-assistent_HR_IurO.pdf

[^3]: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/

[^4]: https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger/

[^5]: https://docs.n8n.io/advanced-ai/rag-in-n8n/

[^6]: https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstoresupabase/

[^7]: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/callback-operations/

[^8]: https://docs.n8n.io/workflows/export-import/

[^9]: https://www.n8nshow.com/en/docs/integrations/builtin/app-nodes/n8n-nodes-base.telegram

[^10]: https://github.com/n8n-io/n8n/blob/master/packages/nodes-base/nodes/Telegram/TelegramTrigger.node.ts

[^11]: https://n8n-docs.teamlab.info/integrations/builtin/app-nodes/n8n-nodes-base.telegram/chat-operations/

[^12]: https://www.n8nshow.com/en/docs/integrations/builtin/app-nodes/n8n-nodes-base.telegram/file-operations

[^13]: https://deepwiki.com/n8n-io/n8n-docs/6.2-vector-databases

[^14]: https://community.n8n.io/t/n8n-telegram-inline-keyboard-callback-query-workflow-example/112588

[^15]: https://n8n-docs.teamlab.info/integrations/builtin/app-nodes/n8n-nodes-base.telegram/callback-operations/

[^16]: https://www.youtube.com/watch?v=8etrLpDB10A

[^17]: https://github.com/n8n-io/n8n/issues/19955

[^18]: https://latenode.com/blog/low-code-no-code-platforms/n8n-setup-workflows-self-hosting-templates/n8n-import-workflow-json-complete-guide-file-format-examples-2025

[^19]: https://n8nstore.net/en/workflow/7664

[^20]: https://www.youtube.com/watch?v=tkInn95k1J4

