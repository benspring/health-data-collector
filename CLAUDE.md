# Oura & 8Sleep data collector
- collect.py pulls Oura and 8Sleep data into data/
- Run: python3 collect.py --start <YYYY-MM-DD> --end <YYYY-MM-DD>
- Use a rolling 90-day window ending today.
- Output format: JSON under `data/` — timestamped snapshots (`oura_<UTC>.json`, `eight_sleep_<UTC>.json`) plus always-overwritten latest copies (`oura_latest.json`, `eight_sleep_latest.json`). Oura payload has `personal_info` and `collections` (daily_sleep, daily_readiness, daily_activity, daily_spo2, daily_stress, sleep, workout, session). Eight Sleep payload has `me` (profile) and `trends` (per-night `days` with score, stages, HR, HRV, etc.).
