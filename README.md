# Salon Scheduler

A reusable scheduling workspace for a small salon: shared day/week calendars, chair assignments, client profiles, appointment history, conflict checks, and optional email reminders.

Built with Python’s standard library, SQLite, and a browser interface with no frontend build step. An optional, fictional marketing website is included in `Website/`.

> **Demo software, not a public client portal.** There is no application login or role-based access control. Anyone who can reach the dashboard can read and change client information. Run locally with fictional data, or put an appropriate private access boundary in place before using real records. Publishing this source code does not mean exposing the running dashboard to the internet.

## Features

- Shared day and week calendars with stylist filters.
- Appointment creation, editing, cancellation, and overlap checks.
- Chair assignment and editable team members.
- Client contact profiles, notes, active/inactive state, and service history.
- SQLite persistence and optimistic client-edit checks.
- Optional SMTP reminders with mocked delivery in tests.
- Docker health checks, non-root application runtime, and persistent storage.

New databases contain three **fictional** stylist profiles and four chairs. Clients and appointments start empty. No customer records, existing database, third-party photos, or business-specific contact details are distributed.

## Start a separate Docker demo

Requires Docker with Compose v2. This example uses its own project and storage; do not reuse an existing business database or volume.

```sh
cp .env.example .env
# Edit your private .env if the example ports are already used.
docker compose up -d --build --wait
```

Open http://127.0.0.1:18093. Optional website: `docker compose --profile website up -d --build --wait`, then open http://127.0.0.1:18094.

Both bind to loopback by default. Example ports, filesystem paths, timezone, and hardware requirements may differ in your environment. Docker builds for the host architecture when the selected base image supports it; no particular Mac or operating system is required for the core app.

The demo project is named `salon-scheduler-demo`. Application data is stored in that project’s `salon-data` volume. `docker compose down` keeps it; `docker compose down -v` deletes it. The optional website is static and does not submit appointments to the dashboard.

## Run without Docker

Python 3.9 or newer; no package installation required:

```sh
python3 server.py
```

Open http://127.0.0.1:8000. By default the database is created at `data/salon.sqlite3`. `HOST`, `PORT`, and `SALON_DB` customize the process listener and data path. Direct Python execution does not load `.env`; set environment variables in the shell or service manager.

The included HTTP server is suitable for local demonstrations. A production deployment requires a reviewed serving/access setup, HTTPS where applicable, and a plan for protecting client data. Devices sharing the calendar should use the same display timezone; booking times render in each browser’s local timezone.

## Email reminders

Email is disabled when SMTP settings are blank. For a controlled deployment, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, and, if required, `SMTP_USER` and `SMTP_PASSWORD` in private runtime configuration. Set `SALON_TIMEZONE` to your own timezone; the generic example uses `Etc/UTC`.

The worker checks once per minute for eligible confirmed appointments in the next 72 hours. Completed and cancelled appointments are excluded. Changing an appointment’s time or email resets reminder state. Successful delivery is recorded, but interruption after SMTP acceptance can result in a retry and duplicate message.

Tests mock SMTP; no real recipients or mail credentials are supplied. Leave SMTP disabled for public demonstrations and use sample data only.

## Backups

Back up SQLite consistently using its backup API or with the application stopped. Keep backups, exports, logs, `.env` files, and customer screenshots outside Git. The ignore rules help prevent accidental additions but do not remove already committed files.

For an existing deployment, plan storage mapping and data migration separately. Do not launch a second writable instance against its database as a shortcut to testing.

## Optional macOS updater

`scripts/auto-update.py` and `scripts/install-auto-update.py` are optional host tools for a **dedicated demo clone**. They are not installed by starting Docker.

The updater fetches a configured branch, stages a release, builds and tests an image, backs up the database, and attempts a healthy rollout. A failed rollout attempts to restore the previous image; it does not roll back database mutations. Changes to database schemas must remain compatible with the previous release. Installation requires deliberate host access and authenticated Git access.

`UPDATE_BRANCH` defaults to `main` for an independently published repository. If testing this branch inside the original private repository, set `UPDATE_BRANCH=public-ready`. The demo’s Compose project, image names, LaunchAgent label, and log folder are separate from the original deployment. Do not install a second updater for the same stack or copy these scripts into a live deployment without reviewing them.

## Verification

```sh
python3 -m unittest discover -s tests -v
docker compose config --quiet
node --check public/app.js
node --check Website/public/app.js
```

Tests use temporary databases and cover client persistence, appointment edits and conflicts, reminder behavior, and updater failure/rollback paths.

## Repository layout

| Path | Purpose |
| --- | --- |
| `server.py` | HTTP API, SQLite state, and reminder worker |
| `public/` | Dashboard UI and original demo SVG mark |
| `Website/` | Fictional marketing template with no real contact or booking destination |
| `tests/` | Backend and mocked updater tests |
| `scripts/` | Optional demo deployment helpers |
| `PUBLICATION.md` | Publication scope and clean-history handling |

This is a generalized code example, not an endorsement of, or a claim to represent, an operating salon. No reuse license has been selected in this preparation step.
