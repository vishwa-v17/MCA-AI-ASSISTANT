# MCA AI ASSISTANT

Existing Flask-based MCA student AI assistant using **OpenRouter**.

This version keeps the existing Flask application, authentication, chat sessions, chat history, subjects, uploads, system prompt, streaming responses, and UI. The main change is secure OpenRouter credential management and dynamic model selection.

## Features

- Web-based AI chat with streaming responses
- Existing login/register and user sessions
- Existing MCA subjects and study generators
- OpenRouter integration
- Server-side default OpenRouter API key
- Optional personal OpenRouter API key per user
- Personal keys encrypted before database storage
- Personal keys isolated by authenticated user ID
- Dynamic OpenRouter model catalog
- Dynamically detected free text models
- `openrouter/free` Free Router option
- Model search/filter
- Per-user model preference
- Configurable per-user rate limits for shared server access
- Existing system prompt remains in `system-prompt.txt`

## How OpenRouter access works

### Normal user

1. Create an account.
2. Log in.
3. Start chatting immediately.
4. No personal API key is required.

When the user has no personal key, the backend reads `OPENROUTER_API_KEY` from the server environment and sends the request to OpenRouter. The server key is never returned to the browser.

### Optional personal API key

1. Open **Settings**.
2. Enter your own OpenRouter API key.
3. Click **Validate Key** if desired.
4. Choose an available model.
5. Click **Save Settings**.

The personal key is encrypted before it is stored in SQLite. The decrypted key exists only on the server while an OpenRouter request is being made.

### Return to server default

1. Open **Settings**.
2. Click **Remove Personal Key**.

The personal key is deleted and the account automatically falls back to the server default key. The selected model preference can remain unchanged.

## Model selection

The backend retrieves the current OpenRouter model catalog from:

`https://openrouter.ai/api/v1/models`

The list is cached server-side so the catalog is not downloaded for every chat request.

The Settings model selector contains:

- **Recommended Free Models** — determined dynamically from current zero-cost text input/output pricing.
- **OpenRouter Free Router** — `openrouter/free`, which automatically selects an available free model.
- **All Available Models** — current catalog entries.

Model IDs sent by the browser are validated against the current catalog before being saved or used.

## Environment variables

Create a local `.env` file for development or configure these values in your hosting provider:

```text
OPENROUTER_API_KEY=
USER_KEY_ENCRYPTION_SECRET=
DEFAULT_OPENROUTER_MODEL=openrouter/free
OPENROUTER_MODEL_CACHE_TTL=900
AI_RATE_LIMIT_PER_MINUTE=10
AI_RATE_LIMIT_PER_HOUR=100
MAX_AI_MESSAGE_LENGTH=12000
SECRET_KEY=
```

A template is provided in `.env.example`.

### Important

Never commit `.env`.

Never put a real OpenRouter key in:

- Python source
- HTML
- JavaScript
- CSS
- `smartgpt_config.json`
- SQLite
- GitHub
- URLs
- chat history
- logs

`USER_KEY_ENCRYPTION_SECRET` is required if personal keys are stored. Keep it stable: changing it later makes previously encrypted personal keys undecryptable.

For Render, add the environment variables in the service's **Environment** settings. Do not put the real values into GitHub.

## Local setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set:

```text
OPENROUTER_API_KEY=your_server_openrouter_key
USER_KEY_ENCRYPTION_SECRET=your_long_random_secret
DEFAULT_OPENROUTER_MODEL=openrouter/free
```

Then run:

```bash
python app.py
```

Open:

`http://127.0.0.1:5000`

For production with Gunicorn:

```bash
gunicorn "app:create_app()"
```

## Existing database

The existing `mca_assistant.db` is not reset.

On startup, the database initialization code creates/migrates the user AI configuration table as needed. Existing users, sessions, messages, subjects, and other application data are preserved.

Older versions of the project used a plaintext `api_key` column. The migration encrypts legacy values using `USER_KEY_ENCRYPTION_SECRET` and rebuilds the table without the plaintext column.

If an old database actually contains personal API keys, configure `USER_KEY_ENCRYPTION_SECRET` before starting the upgraded application so those keys can be migrated securely.

## Security model

### Server default key

The default key is read only from:

`OPENROUTER_API_KEY`

It is never sent to the frontend.

### Personal user key

The personal key is:

1. Submitted over the authenticated HTTPS application connection.
2. Validated with OpenRouter.
3. Encrypted with Fernet-derived encryption using `USER_KEY_ENCRYPTION_SECRET`.
4. Stored as encrypted database data.
5. Decrypted only on the server immediately before an OpenRouter request.

The frontend receives only safe status such as:

- `Using default server key`
- `Using your personal OpenRouter key`
- masked last-four-character information for a personal key

The complete key is never returned by `/api/config`.

The key is not stored in `localStorage`, `sessionStorage`, cookies, URLs, or chat messages.

## Rate limiting

Requests that use the shared server key are limited per authenticated user.

Defaults:

- 10 requests per minute
- 100 requests per hour
- 12,000 characters maximum per message

These values are configurable through environment variables.

If a user uses a personal key, the shared-server-key rate limiter does not consume the server's shared quota for that request.

## Important hosting configuration

Set these in the hosting provider's environment-variable section:

```text
OPENROUTER_API_KEY=...
USER_KEY_ENCRYPTION_SECRET=...
DEFAULT_OPENROUTER_MODEL=openrouter/free
```

Do not create a website page that edits `OPENROUTER_API_KEY`. Change the server key only through hosting infrastructure environment variables.

## Verification checklist

### New user

- Register.
- Log in.
- Do not add a personal key.
- Chat immediately.
- Backend uses the server default key.

### Personal key

- Log in as User A.
- Validate and save a personal key.
- Send a chat request.
- Backend uses User A's key.

### Second user

- Log in as User B.
- Do not configure a personal key.
- Backend uses the server default key.
- User B cannot retrieve User A's key.

### Remove key

- User A removes the personal key.
- Subsequent requests automatically use the server default.

### Model change

- Select one model.
- Save.
- Select another model.
- Save.
- Subsequent requests use the latest validated model.

### Security inspection

Check browser Network, Local Storage, Session Storage, cookies, HTML, JavaScript, database contents, and application logs.

The server default key and decrypted personal keys must not appear in any client-visible location or logs.

## Project structure relevant to the OpenRouter change

```text
app/
├── routes/
│   ├── chat.py
│   ├── config.py
│   └── subjects.py
└── services/
    ├── db_service.py
    ├── key_service.py
    ├── llm_service.py
    ├── openrouter_service.py
    └── rate_limiter.py

database.py
smartgpt_config.json
.env.example
system-prompt.txt
templates/index.html
static/script.js
```
