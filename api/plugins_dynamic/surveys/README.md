# yfw-surveys

Survey builder plugin for [YourFinanceWORKS](https://yourfinanceworks.com). Create surveys, share public links, collect responses, and export results as CSV.

Runs in two modes:

- **Plugin**: installed into the YFW host app — uses YFW auth and mounts on its FastAPI instance
- **Standalone**: independent Docker service — connects to YFW for auth validation

## Features

- Build surveys with 6 question types: short text, paragraph, multiple choice, checkboxes, rating (1–5), yes/no
- Share public survey links (no login required for respondents)
- View and filter responses in the management UI
- Export all responses as CSV
- Required question validation on submission
- Survey expiry dates and active/inactive toggle

## Quick Start (Standalone)

```bash
cp .env.example .env
# Edit .env: set YFW_API_URL and YFW_API_KEY
docker-compose -f standalone/docker/compose.yml up
```

- API: [http://localhost:8001/docs](http://localhost:8001/docs)
- UI:  [http://localhost:3001](http://localhost:3001)

## Plugin Installation

1. Clone into `api/plugins/surveys/` inside your YFW repo
2. The YFW plugin loader will discover `plugin.json` and call `register_plugin(app)`
3. Set `SURVEYS_DATABASE_URL` in your YFW environment (default: `sqlite:///./surveys.db`)
4. The plugin UI page (`plugin/ui/SurveysPage.tsx`) can be loaded by the YFW frontend plugin system

## Development

```bash
# Backend
pip install -r requirements.txt
uvicorn standalone.main:app --reload --port 8001

# Frontend
cd standalone/ui
npm install
npm run dev
```

## API Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/surveys` | ✓ | List all surveys |
| POST | `/api/v1/surveys` | ✓ | Create a survey |
| GET | `/api/v1/surveys/{id}` | ✓ | Get survey with questions |
| PUT | `/api/v1/surveys/{id}` | ✓ | Update survey |
| DELETE | `/api/v1/surveys/{id}` | ✓ | Delete survey |
| POST | `/api/v1/surveys/{id}/questions` | ✓ | Add a question |
| PUT | `/api/v1/surveys/{id}/questions/{qid}` | ✓ | Update a question |
| DELETE | `/api/v1/surveys/{id}/questions/{qid}` | ✓ | Delete a question |
| GET | `/api/v1/surveys/{id}/responses` | ✓ | List responses |
| GET | `/api/v1/surveys/{id}/responses/{rid}` | ✓ | Get response detail |
| GET | `/api/v1/surveys/{id}/export` | ✓ | Download responses CSV |
| GET | `/api/v1/surveys/public/{slug}` | — | Get survey form (public) |
| POST | `/api/v1/surveys/public/{slug}/submit` | — | Submit response (public) |

## Database Tables

- `surveys` — survey definitions
- `survey_questions` — questions per survey
- `survey_responses` — individual submissions
- `survey_answers` — per-question answers

Configure via `SURVEYS_DATABASE_URL`. Defaults to SQLite (`surveys.db`). Switch to Postgres by setting `SURVEYS_DATABASE_URL=postgresql://user:pass@host/db`.

## Troubleshooting

### "Cannot reach YFW at http://localhost:8000"

This error occurs when the standalone survey app cannot connect to the main YourFinanceWORKS API to validate your API key.

**Solutions:**

1. **Start the main YFW app**: Ensure the main API is running on port 8000.
2. **Use the Demo instance**: Set `YFW_API_URL=https://demo.yourfinanceworks.com` in your `.env` file.
3. **Use Mock Mode**: Set `MOCK_YFW_API=true` in `.env` to bypass the connection check during local development.
4. **Use Development Mode**: Set `DEVELOPMENT_MODE=true` and use `ak_dev` as your API key.
