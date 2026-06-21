# AI-Powered LinkedIn Outreach Automation

Local, configurable Python 3.12 project for personalized LinkedIn connection outreach using Playwright, Google Sheets, SQLite, APScheduler, Loguru, and an LLM provider abstraction for OpenRouter, OpenAI, and Anthropic.

This repository is designed for responsible local operation. LinkedIn automation can violate platform rules or account safety expectations. The software includes throttles, dry-run mode, screenshots, state tracking, and explicit safety switches, but it does not claim to be undetectable.

## What It Does

1. Reads target rows from Google Sheets.
2. Opens LinkedIn with Playwright using persistent local browser state.
3. Extracts visible profile context such as name, headline, current role, mutual connections, and activity.
4. Opens recent activity, collects latest visible posts, likes 2-3 posts if enabled, and drafts a contextual comment.
5. Reviews the comment through a second LLM pass before posting.
6. Drafts a connection request note, reviews it, humanizes wording, validates length and tone, then sends the request.
7. Updates Google Sheets and SQLite with status, timestamps, generated note, generated comment, run ID, and errors.
8. Runs a follow-up job after 14 days to detect accepted requests and optionally withdraw pending requests.

## Repository Layout

```text
agents/                 LLM-powered note/comment agents and humanization
config/config.yaml       Runtime behavior, selectors, safety limits, delays
database/schema.sql      SQLite schema
jobs/                    CLI entrypoints for outreach and follow-up
models/schemas.py        Pydantic models and settings
repositories/            SQLite repository pattern
services/                Browser, LinkedIn, Sheets, LLM, scheduler, logging services
templates/               Google Sheet CSV template
tests/                   Unit and integration-style tests with mocks
utils/                   Retry, timers, stealth helpers, selectors, validators
```

## Installation

### macOS

```bash
cd "/Users/anantbhujade/Desktop/JOB/Companies/AI Assignment"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

### Linux

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv
cd "/path/to/AI Assignment"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
cp .env.example .env
```

### Windows PowerShell

```powershell
cd "C:\path\to\AI Assignment"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

## Docker Setup

```bash
cp .env.example .env
docker compose build
docker compose run --rm linkedin-outreach
docker compose --profile followup run --rm linkedin-followup
```

For visible browser login, local Python is usually easier than Docker. Docker headful browser support requires additional host display configuration.

## Google Service Account Setup

1. Create a Google Cloud project.
2. Enable Google Sheets API.
3. Create a service account.
4. Generate a JSON key.
5. Save it as `secrets/google-service-account.json`.
6. Share your Google Sheet with the service account email.
7. Copy `templates/linkedin_targets_template.csv` headers into the first row.
8. Set `.env`:

```env
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_WORKSHEET_NAME=Targets
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
```

Required input columns:

```text
linkedin_url, first_name, company, notes
```

Written output columns:

```text
status, sent_timestamp, accepted_timestamp, withdrawn_timestamp,
generated_note, generated_comment, error_message
```

## LLM Setup

Choose one provider in `.env`.

### OpenRouter

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
```

### Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
```

### Local Mock Provider

For code review, offline demos, or no-cost dry runs, use:

```env
LLM_PROVIDER=mock
DRY_RUN=true
GOOGLE_SHEET_ID=
LOCAL_TARGETS_CSV=templates/linkedin_targets_template.csv
```

This mode uses deterministic local text generation and reads targets from the CSV template instead of Google Sheets. It is useful for validating orchestration without sending API calls to paid LLM providers.

## LinkedIn Login

Default configuration uses manual login:

```yaml
safety:
  require_manual_login: true
```

Run the outreach job. A browser opens. Complete LinkedIn login manually. The browser profile is saved under `.browser/linkedin`, so later runs can reuse the session.

## Running Outreach

```bash
source .venv/bin/activate
python -m jobs.run_outreach
```

Start in dry-run mode:

```env
DRY_RUN=true
```

Dry-run prepares comments and notes but does not submit final connection requests. In dry-run mode, real post likes are skipped as well. Set `DRY_RUN=false` only after validating selectors and behavior with your own test profile list.

## Running Follow-Up

```bash
python -m jobs.run_followup
```

The follow-up job checks SQLite for pending requests older than `scheduler.followup_after_days` in `config/config.yaml`. Withdrawal is disabled by default:

```yaml
safety:
  allow_withdrawals: false
```

Set it to `true` only if you have reviewed the workflow and are comfortable with automated withdrawals.

## Safety Settings and Rate Limits

Configured in `config/config.yaml`:

```yaml
safety:
  daily_connection_limit: 20
  daily_comment_limit: 25
  max_profiles_per_run: 10
```

Delays are also configurable:

```yaml
delays:
  between_profiles_seconds_min: 120
  between_profiles_seconds_max: 300
  within_profile_seconds_min: 2
  within_profile_seconds_max: 10
  typing_delay_ms_min: 50
  typing_delay_ms_max: 150
```

The automation uses random viewport sizes, mouse movement, scrolling, idle pauses, natural click delays, and typing delays. These are safety and ergonomics controls, not a guarantee of avoiding platform detection.

## Expected Outputs

Google Sheet rows are updated with:

```text
status=request_sent
sent_timestamp=2026-06-21T10:15:00+00:00
generated_note=Hi Alex, I saw your work in AI infrastructure...
generated_comment=The operational angle here is useful...
error_message=
```

SQLite is stored at:

```text
database/outreach.sqlite3
```

Logs are written to:

```text
logs/app.log
```

Failure screenshots are written to:

```text
screenshots/
```

Example console logs:

```text
2026-06-21 10:00:00 | INFO | Started outreach run 6a7...
2026-06-21 10:00:08 | WARNING | Manual LinkedIn login required...
2026-06-21 10:04:21 | INFO | DRY_RUN enabled; connection request prepared but not sent
```

## Testing

```bash
pytest
```

The tests cover validation, SQLite persistence, LLM response parsing with mocked HTTP, and agent review/humanization behavior.

## Troubleshooting

`Google service account file not found`: create `secrets/google-service-account.json` and confirm the path in `.env`.

`Worksheet not found`: create a tab named `Targets` or update `GOOGLE_WORKSHEET_NAME`.

`LLM provider missing API key`: set the key for the provider selected by `LLM_PROVIDER`.

`LinkedIn login loop`: delete `.browser/linkedin`, rerun, and complete login manually.

`Selectors stopped working`: LinkedIn UI changes frequently. Update `config/config.yaml` selectors without changing code.

`Browser closes too quickly`: keep `DRY_RUN=true`, use `headless: false`, and inspect screenshots plus `logs/app.log`.

## Screenshots

Screenshots are captured automatically only on failure. They are stored under `screenshots/` and referenced in the Google Sheet error column.
