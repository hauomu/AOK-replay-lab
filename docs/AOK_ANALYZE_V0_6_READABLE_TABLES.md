# AoK `/aok_analyze` v0.6 — readable Markdown tables

## Purpose

v0.6 makes the generated Markdown report easier to read by replacing the previous very-wide evidence tables with smaller themed tables.

## Table formatting choice

Use **Jinja2** for report templating.

NumPy is not the right tool here because the problem is presentation/layout, not numerical array computation. Jinja2 lets the bot separate report structure from replay/stat logic and makes it easier to refine the report format later.

## New report layout

The attached Markdown report now splits evidence into:

- Team/side overview
- Side combat + activity
- Side army / defense footprint
- Player 15 / Animals evidence
- Player overview
- Player combat + activity
- Player army profile
- Timeline snapshots
- Player composition details

The Discord embed remains summary-first. The detailed numbers stay in the Markdown attachment.

## Dependency

`discord_bot/requirements.txt` now includes:

```text
Jinja2>=3.1.4
```

Existing local users should run:

```powershell
cd "$env:USERPROFILE\Desktop\AOK-replay-lab\discord_bot"
$Python = "$PWD\.venv311\Scripts\python.exe"
& $Python -m pip install -r requirements.txt
```

If Jinja2 is not installed yet, the bot falls back to a compact non-template Markdown report instead of crashing.
