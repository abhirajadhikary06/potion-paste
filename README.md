# Potion Paste

**Collaborative code snippet sharing** — private by default, offline-capable PWA, real-time comments, revision history, and shareable links.

Inspired by modern developer workspace UIs (clean typography, generous whitespace, dark title bars, soft cards). Built as a production-minded Flask + vanilla JS application ready for local development and AWS deployment.

---

## Features

- **Snippets**: create, edit, delete, tag, language selection, revision history
- **Privacy**: private by default; non-guessable share IDs + optional share tokens with expiry / view limits
- **Auth**: email/username + password with **Argon2id**, HTTP-only session cookies, CSRF protection
- **Comments**: threaded-capable comments with real-time delivery via Socket.IO
- **Real-time**: WebSocket rooms for snippet updates and new comments
- **PWA / Offline**: service worker, web app manifest, IndexedDB cache, pending operation queue with version-based conflict detection
- **Syntax highlighting**: Prism.js (30+ languages)
- **Editor UX**: line numbers, tab insertion, copy-to-clipboard, autosave-ready
- **Landing page**: polished marketing page matching the supplied visual language

---

## Project structure

```
potion-paste/
├── backend/
│   ├── app/
│   │   ├── api/          # snippets, comments, share, sync routes
│   │   ├── auth/         # register / login / profile
│   │   ├── models/       # User, Snippet, Comment, ShareLink, SyncOperation…
│   │   ├── services/
│   │   ├── utils/
│   │   ├── config.py
│   │   └── __init__.py   # app factory + SocketIO
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   ├── run.py
│   └── wsgi.py
├── frontend/
│   ├── index.html        # Landing
│   ├── app.html          # Application shell
│   ├── css/main.css
│   ├── js/{app,editor,offline}.js
│   ├── sw.js
│   ├── manifest.json
│   └── icons/
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Quick start (local)

### Prerequisites
- Python 3.11+
- PostgreSQL 14+ (or use Docker)
- Redis (optional for multi-worker SocketIO; not required for single-process dev)

### 1. Database

```bash
# With Docker
docker compose up -d db redis

# Or local Postgres
createdb potion_paste
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit SECRET_KEY and DATABASE_URL if needed

export FLASK_APP=app
flask db upgrade

python run.py
```

App runs at **http://localhost:5000**

- Landing: `/`
- App: `/app`
- Health: `/api/health`

When you change database models, create a new migration with `flask db migrate -m "describe change"`, then apply it with `flask db upgrade`. The existing `backend/migrations/` directory is already initialized; do not run `flask db init` again.

### 3. Full stack via Docker

```bash
docker compose up --build
```

---

## Environment variables

See `backend/.env.example`. Important ones:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session / CSRF signing |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | SocketIO message queue (production) |
| `FRONTEND_ORIGIN` / `ALLOWED_ORIGINS` | CORS |
| `SESSION_COOKIE_SECURE` | Set `True` behind HTTPS |

Never commit real secrets. Use AWS Secrets Manager in production.
Production startup requires a non-placeholder `SECRET_KEY` of at least 32 characters.

---

## API overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET  | `/api/auth/me` | Current user |
| GET  | `/api/snippets` | List own snippets |
| POST | `/api/snippets` | Create |
| GET  | `/api/snippets/:id` | Get (auth or share token) |
| PATCH| `/api/snippets/:id` | Update |
| DELETE| `/api/snippets/:id` | Delete |
| GET  | `/api/snippets/:id/comments` | List comments |
| POST | `/api/snippets/:id/comments` | Add comment |
| POST | `/api/snippets/:id/share` | Create share link |
| POST | `/api/sync/push` | Apply offline ops |
| GET  | `/api/sync/pull` | Pull recent changes |
| GET  | `/api/csrf-token` | CSRF for SPA |

WebSocket events: `join_snippet`, `snippet:updated`, `comment:created`, …

---

## Offline & conflict strategy

1. Service worker caches the app shell and static assets.
2. IndexedDB stores recently viewed/edited snippets.
3. Offline creates/updates/deletes are written to a `pending_ops` store with unique `op_id` and `client_version`.
4. On reconnect, `/api/sync/push` applies ops. If server `version > client_version`, the op is marked `conflict` and left for the user to resolve (no silent overwrite).

---

## AWS deployment (practical first version)

| Concern | Service |
|---------|---------|
| HTTP + WebSocket API | **API Gateway HTTP API** + **Lambda** (or ECS/Fargate for long-lived SocketIO) |
| Database | **Amazon RDS PostgreSQL** |
| Static assets | **S3** + **CloudFront** |
| Secrets | **Secrets Manager** |
| Logs / metrics | **CloudWatch** |
| IAM | Least-privilege roles for Lambda → RDS / S3 / Secrets |

**Notes for WebSockets on AWS**

- Pure Lambda + API Gateway WebSocket API works for request/response style messaging.
- For Socket.IO with rooms and long-lived connections, prefer a small **ECS Fargate** or **Elastic Beanstalk** service running `gunicorn` + `eventlet`/`gevent`, fronted by an Application Load Balancer with sticky sessions, or use Redis as the Socket.IO message queue across workers.

**Suggested flow**

1. Build static frontend → upload to S3 → CloudFront distribution.
2. Package Flask with Zappa / AWS SAM / Serverless Framework *or* run on Fargate.
3. Point API Gateway / ALB to the backend.
4. Store `DATABASE_URL`, `SECRET_KEY`, etc. in Secrets Manager; inject at runtime.
5. Enable HTTPS everywhere; set `SESSION_COOKIE_SECURE=True`.

Keep architecture minimal: one RDS instance, one compute service, S3+CloudFront, Secrets Manager, CloudWatch.

---

## Security checklist

- [x] Argon2id password hashing
- [x] HTTP-only, SameSite cookies
- [x] CSRF tokens for mutating requests
- [x] Authorization checks on every snippet/comment mutation
- [x] Non-guessable share identifiers
- [x] Input length limits + bleach sanitization
- [x] No secrets in frontend code
- [ ] Rate limiting (add in production with Redis)
- [ ] Email verification (optional next step)

---

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Development notes

- Frontend is intentionally **vanilla HTML/CSS/JS** for simplicity and PWA friendliness.
- Design tokens live in `frontend/css/main.css` (`:root`).
- Real-time is optional via `ENABLE_WEBSOCKETS`.
- For production, serve the frontend from CloudFront and the API from a separate origin; update `ALLOWED_ORIGINS` accordingly.

---

## License

MIT — use freely for personal or commercial projects.
