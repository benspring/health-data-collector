# Sleep data collector

Pulls your **Oura Ring** and **Eight Sleep** data into local JSON files.

## Setup

```bash
cd /Users/benspring/Local/data-collector
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Oura (official API, OAuth2)

Personal access tokens were deprecated. You need a developer app:

1. Create an application at [cloud.ouraring.com/oauth/applications](https://cloud.ouraring.com/oauth/applications)
2. Set redirect URI to `http://localhost:8787/callback`
3. Put `OURA_CLIENT_ID` and `OURA_CLIENT_SECRET` in `.env`
4. Authorize once:

```bash
python auth_oura.py
```

That stores `OURA_ACCESS_TOKEN` / `OURA_REFRESH_TOKEN`. The collector refreshes tokens automatically.

### Eight Sleep (unofficial app API)

Eight Sleep has no public developer API. This uses the same private endpoints as the mobile app (same approach as Home Assistant / pyEight). Use only with your own account.

Put in `.env`:

- `EIGHT_SLEEP_EMAIL`
- `EIGHT_SLEEP_PASSWORD`
- `EIGHT_SLEEP_TIMEZONE` — IANA name such as `America/New_York` (required for trends)

## Collect

```bash
python collect.py                  # both sources, last 7 days
python collect.py --source oura
python collect.py --source eight
python collect.py --start 2026-09-01 --end 2026-09-27
```

Writes under `data/`:

- `oura_<timestamp>.json` + `oura_latest.json`
- `eight_sleep_<timestamp>.json` + `eight_sleep_latest.json`

Oura collections include daily sleep, readiness, activity, SpO2, stress, plus sleep sessions, workouts, and personal info.

Eight Sleep returns profile (`me`) and nightly trends (score, stages, HR, HRV, respiratory rate, etc.).
