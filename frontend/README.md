# MarkBridge Frontend

Vite + React frontend for the MarkBridge parsing workspace.

## Environment
Create `.env.local` from `.env.example`.

```bash
cp .env.example .env.local
```

Default API base:

```bash
VITE_MARKBRIDGE_API_BASE=http://localhost:8000
```

## Run
```bash
npm install
npm run dev
```

## Expected Backend
Run the MarkBridge FastAPI backend separately:

```bash
python3 -m markbridge.api
```

The UI expects:
- `GET /health`
- `GET /v1/runtime-status`
- `GET /v1/s3/objects`
- `POST /v1/parse/upload`
- `POST /v1/parse/s3`
