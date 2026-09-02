# Cloud Deployment Guide

This guide describes how to deploy AI RAG Platform to a cloud environment
without a local GPU, using OpenAI as the LLM provider.

## Architecture (Cloud)

```
Client → Railway/Render/VPS
              ├── FastAPI app   (this repo)
              ├── PostgreSQL    (Supabase / Railway Postgres / managed)
              ├── Qdrant        (Qdrant Cloud free tier)
              └── OpenAI API    (gpt-4o-mini + text-embedding-3-small)
```

## Option A: Railway (recommended)

### 1. Prerequisites

- [Railway account](https://railway.app)
- [Qdrant Cloud account](https://cloud.qdrant.io) (free tier available)
- OpenAI API key

### 2. Create services on Railway

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Create a new project
railway init

# Add PostgreSQL plugin
railway add --plugin postgresql

# Deploy the app
railway up
```

### 3. Environment variables on Railway

In the Railway dashboard → your service → Variables, set:

```
# Database (auto-provided by Railway Postgres plugin as DATABASE_URL)
DATABASE_URL=<auto-set by Railway>

# Qdrant Cloud
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key

# LLM Provider: switch to OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Auth
JWT_SECRET_KEY=<generate: openssl rand -hex 32>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
DEMO_MODE_ENABLED=true

# Worker
DOCUMENT_WORKER_ENABLED=true
```

### 4. Run migrations on Railway

```bash
railway run alembic upgrade head
```

---

## Option B: Render

### 1. Create a Web Service

In Render dashboard:
- **Environment**: Python 3
- **Build command**: `pip install -r requirements.txt`
- **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 2. Add a PostgreSQL database

Use Render's managed PostgreSQL. Copy the `DATABASE_URL` to your Web Service's environment variables.

### 3. Environment variables

Same as Railway above. Add `PORT=8000` if not auto-set.

---

## Option C: VPS (any cloud VM)

### 1. Clone and configure

```bash
git clone https://github.com/roman-nalapko/ai-rag-platform.git
cd ai-rag-platform
cp .env.example .env
# Edit .env — set LLM_PROVIDER=openai, OPENAI_API_KEY, etc.
```

### 2. Run with Docker Compose

```bash
docker compose up -d
docker compose exec app alembic upgrade head
```

---

## Qdrant Cloud Setup

1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a free cluster
3. Copy the cluster URL and API key
4. Set in environment:
   ```
   QDRANT_URL=https://your-cluster.qdrant.io:6333
   QDRANT_API_KEY=your-key
   ```

> [!NOTE]
> The app uses the Qdrant async client. The `QDRANT_API_KEY` is passed automatically
> when the URL is a cloud URL. You may need to update `app/rag/vector_store.py` to
> pass the `api_key` parameter if your Qdrant Cloud cluster requires it.

---

## Cost Estimate (OpenAI)

For a demo/portfolio workload with low traffic:

| Resource | Cost |
|---|---|
| `gpt-4o-mini` (~500 QA requests/month) | ~\$0.10 |
| `text-embedding-3-small` (~1000 doc chunks) | ~\$0.02 |
| Railway Hobby plan | \$5/month |
| Qdrant Cloud free tier | \$0 |
| **Total** | ~\$5–6/month |

---

## Verifying the deployment

```bash
# Health check
curl https://your-app.railway.app/health

# Register a user
curl -X POST https://your-app.railway.app/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "yourpassword"}'

# Open demo UI
open https://your-app.railway.app/demo/
```
