# Northbound
Private single-user internship research and application workspace for Dragoș Geica, Summer 2027. Flask, SQLite (WAL), Waitress, vanilla JavaScript. No paid services, analytics, automatic outreach or public deployment.

## Start on your Mac (first time)

The cloud workspace and your Mac are separate computers. The `/workspace/...` folder exists only in the cloud. Downloading this repository gives your Mac the app code; your cloud password and private database are deliberately not included.

1. Install Python **3.12 or newer** from [python.org](https://www.python.org/downloads/macos/) if it is not already installed. This is a one-time step.
2. On GitHub, select the **main** branch, then **Code → Download ZIP**. Open the downloaded ZIP and keep the extracted `job-applications-main` folder in **Downloads**. If you downloaded an older copy that only contains a README, download it again.
3. Open your Mac's **Terminal**. Paste these commands, then press Enter:

```sh
cd ~/Downloads/job-applications-main
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python app.py --set-password
.venv/bin/python seed_research.py
.venv/bin/python research.py --once
.venv/bin/python app.py
```

When asked for a password, choose at least 12 characters. Terminal hides the letters while you type; this is normal. Press Enter when finished. If `python3` reports an older version despite installing Python 3.12, use `python3.12` for the first command that creates the virtual environment.

4. Leave Terminal running. On **your Mac**, open **http://127.0.0.1:8000** in Safari or Chrome and sign in with the password you just chose. This address works only on the computer running the app; it is not a public website.

The initial research can take a few minutes. A failed source does not prevent you from using the tracker; see **Settings & sources** for diagnostics. A fresh Mac database starts independently from the cloud database. Use JSON backup/restore in the app if you want to transfer records; do not put backups or passwords on GitHub.

### Start again later

You only need these commands in Terminal:

```sh
cd ~/Downloads/job-applications-main
.venv/bin/python app.py
```

Open the same browser address and sign in. Your data is retained in the folder's `data` directory. Do not delete this folder or replace it with a fresh ZIP without first saving a JSON backup. Press **Control+C** in Terminal to stop the app.

### Enable weekly research on your Mac

Open a **second Terminal window**, paste these commands, and leave it running:

```sh
cd ~/Downloads/job-applications-main
.venv/bin/python research.py
```

Weekly runs require your Mac to be awake, connected to the Internet, and running this worker. For updates while your Mac is off, use an always-on host as described below. You can also use **Refresh research** in the app at any time.

### Start in the existing cloud development environment

In the **cloud environment's terminal**, use `cd /workspace/job-applications` instead of the Mac path. Dependencies and the initial database are already prepared. Run `.venv/bin/python app.py` and, in a separate terminal, `.venv/bin/python research.py`. A local Mac browser cannot access the cloud server through its own loopback address. This cloud setup does not provide a supported browser preview link.

The worker runs Monday at 09:00 America/New_York, including DST, and catches up after that week's scheduled time if restarted late. A database marker avoids duplicate weekly runs; an OS file lock prevents concurrent manual/scheduled research. The worker heartbeat is shown in the app. Live processes must be restarted after a cloud machine stops. This environment is not an always-on hosting service.

An initial random local password may already be configured at `data/initial-password.txt` (mode 0600) for the prepared instance. Read it locally or replace it using `--set-password`. Never commit or share that file. Passwords are hashed; authentication secrets are excluded from exports. A new device uses the same single-user login against the same server database. There are no secondary users or public registration. Sessions expire after 12 hours. Changing the password does not invalidate existing sessions until expiration; stop the server and delete `data/session.key` to revoke them immediately.

## Use

- Opportunities: search, combine filters, sort by priority/relevance, deadline or update time; open a row for evidence, restrictions and tracking. Empty/unverified locations are explicit. Quebec is excluded from default results.
- My applications: saved records and progressed applications; independent application/outreach stages; optional Kanban.
- Contacts: add evidence-backed professional contacts, independent comma-separated connection tags, associate multiple opportunities and log interactions/follow-ups. No contacts or identity claims are invented.
- This week: seven-day new/changed opportunities, deadlines within 14 days, and due actions. Settings shows full refresh diagnostics, source excerpts, permit status, CSV exports and JSON backup/restore. Restore replaces data transactionally and saves a pre-restore recovery file.
- “Monitor” is a program, not an opening. Generic program dates and recurring recruiting windows are never deadlines. Personal edits are separate from researched fields; a research refresh never changes notes, stages, interactions, priorities or document links.

## Research and limitations

Initial live research on October 25, 2026 verified official program pages and CRA/Brattle Greenhouse boards. See database source evidence and verification timestamps for exact results. The Brattle official careers page embeds the `thebrattlegroup` Greenhouse board. General careers pages do not confirm a vacancy or office. The seed script inserts two evidence-backed program watchlist records, never fictional openings. Live discoveries depend on sources at runtime.

The weekly worker actually fetches accessible official sources. It discovers via CRA/Brattle public Greenhouse APIs, JobPosting JSON-LD and a bounded set of internship links on employer indices. It extracts only explicitly Canadian non-Quebec work locations and internship titles; remote, ambiguous and unstructured roles need manual review. Multi-office postings stay one record; URL/cycle and employer/requisition/cycle deduplicate. Only an explicit application deadline is treated as a deadline; a generic posting expiry (`validThrough`) is not assumed to be one. A 404, missing result, block or timeout never closes a role. Unknown fields may require manual verification. Source content changes are logged; posting field changes retain previous values. An incomplete discovery run is not evidence that no other vacancies exist.

Greenhouse feeds are configured and require no API key. No comprehensive web-search or contact research service is connected. Contact verification and other ATS platforms (including iCIMS and Workday) remain coverage gaps. French discovery supports French internship titles but bilingual coverage is incomplete. New source hosts must be deliberately approved in `research.fetch` and in environment network settings; arbitrary URLs are not fetched to prevent SSRF. Redirects cannot escape approved hosts or downgrade TLS. No page instructions are executed and no AI model receives private data.

Francophone Mobility explanation is based on the official IRCC employer instructions, checked October 25, 2026. General permit eligibility, an outside-Quebec job, intermediate French speaking/listening (NCLC 5+), and an eligible offer are required. Employer offer submission uses C16 with a $230 employer compliance fee. Eligibility for this user and support by any employer remain unconfirmed. This is not an immigration eligibility decision. Government source text is rechecked weekly; review it if rules change.

## Persistence, migrations and backups

`data/tracker.sqlite3` is the real server database and must reside on a persistent local disk. SQLite supports one always-on server (do not run on ephemeral/serverless disks, network filesystems, or several replicas). `DATABASE_PATH` overrides its location. `store.init()` applies idempotent migration v1, recorded in `migrations`; future schema changes need a new numbered migration. Backups contain private tracking records and should be stored securely. JSON exports exclude passwords/session secrets and preserve all tracker relationships. Restore performs schema and foreign-key validation in one transaction. Keep the database directory private and back it up regularly. CSV cells are escaped against spreadsheet formula injection.

## Always-on deployment (not performed)

No hosting account or paid service has been added. To make the app available across devices and research run while it is closed:

1. Choose an approved always-on Linux host and a domain. Create an unprivileged `northbound` account and copy the repository to `/srv/northbound`; keep `data` private and persistent, owned by that account.
2. Create the venv, install requirements, set a strong password and run the seed and refresh commands as that account. Preserve CA/proxy configuration when applicable; never disable TLS verification.
3. Install the two systemd examples in `deploy/`, then enable and start both `northbound-web` and `northbound-worker`. They deliberately use loopback, not a public Python port.
4. Put an HTTPS reverse proxy in front. `deploy/Caddyfile` is an example requiring your actual domain and DNS. Production web service sets `COOKIE_SECURE=1`. Permit HTTPS only; do not expose port 8000 directly. Do not trust client-supplied forwarding headers.
5. Sign in from a second device, verify a saved edit survives restart, inspect worker heartbeat and a completed refresh, and test encrypted backup recovery before relying on the hosted version.

Publication of a cloud development snapshot does not deploy an always-on web service. No hosted or new-task restoration claim is made.

## Validation

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
node --check static/app.js
```

Tests use isolated temporary databases and simulated changes, never production data. They exercise login and API isolation, CSRF, status updates, contact interactions, relationship backups, atomic invalid restores, deduplication, an unknown deadline becoming known, failed fetch preservation and geography. Browser smoke tests should use a separate temporary database and test credentials. No test contact or opportunity belongs in production.
