# Northbound

## GitHub Pages version

The public website uses IndexedDB to save your application tracking, contacts, notes and interactions **only in your current browser**. There is no login or cross-device sync in this version. Clearing site data removes those records. Export JSON backups regularly through Settings; the website can also import a JSON backup from the local Python app. No personal tracking is sent to GitHub. Public employer research is shared by all visitors.

The `Publish Northbound and refresh research` workflow refreshes research and deploys Pages on pushes to main, on manual runs, and each Monday around 9 a.m. America/New_York. GitHub may delay scheduled runs. Two UTC triggers handle daylight saving time, with only the correct Eastern-time run proceeding. GitHub may disable schedules in public repositories after 60 days without activity; check Actions if research becomes stale.

The website’s refresh button downloads the latest published research; it does not start a server-side research job. To request research immediately, run the workflow through the repository Actions tab. The workflow builds a disposable research-only database, retains the previous public catalogue for fetch failures, and publishes no private database or tracking records. `public-research/research.json` contains only public research. Local-server instructions below still apply to the separate Python version.

Private single-user internship research and application workspace for Dragoș Geica, Summer 2027. Flask, SQLite (WAL), Waitress, vanilla JavaScript. No paid services, analytics, automatic outreach or public deployment.

## Start on your Mac (first time)

The cloud workspace and your Mac are separate computers. The `/workspace/...` folder exists only in the cloud. Downloading this repository gives your Mac the app code; your cloud password and private database are deliberately not included.

1. Download the updated repository: on GitHub select **main → Code → Download ZIP**, then extract it into Downloads. Rename the newly extracted folder **Northbound**. Keep your old folder as a backup; do not overwrite an existing `data` directory if you have already saved records.
2. Open **Terminal** and paste:

```sh
cd ~/Downloads/Northbound
bash start.command
```

The launcher supports **Python 3.9 and newer**, including the Python 3.9 used by many Macs. It installs compatible dependencies, asks you to choose a password on the first run (at least 12 characters), checks initial research sources, and starts the app and its weekly research worker. Password typing is invisible in Terminal; press Enter when finished. If Python is missing, install Python 3.12 from [python.org](https://www.python.org/downloads/macos/).

3. When the terminal says to open the app, visit **http://127.0.0.1:8000** in Safari or Chrome on **this Mac**, and sign in. This address is private to your own computer.

Leave Terminal open. Press **Control+C** to stop both the app and worker. The same two commands start it again later without resetting your password or personal data. Weekly research requires the Mac to be awake and online; for research while it is off, use an always-on host.

### Recover from the old `click==8.5.0` installation error

The older lockfile required packages that do not support Python 3.9. The lockfile has now been resolved and tested for Python 3.9 and newer. The `No module named flask`, `bs4` and `requests` errors were consequences of the failed install, not missing app files. You do not need to delete your database, password or virtual environment.

For an **already downloaded copy**, this immediate recovery uses the existing top-level requirements file, letting pip choose transitive dependencies compatible with your Python:

```sh
cd ~/Downloads/job-applications-main
.venv/bin/python -m pip install -r requirements.txt
```

Wait until installation finishes successfully. If it fails, stop and share that error before running the app. Then set your password **only if you have not set one yet**, and run these commands one at a time:

```sh
.venv/bin/python app.py --set-password
.venv/bin/python seed_research.py
.venv/bin/python research.py --once
.venv/bin/python app.py
```

For this old-copy recovery, start `.venv/bin/python research.py` in a second Terminal window if you want the weekly worker. The updated `start.command` starts it automatically.

A fresh Mac database starts independently from the cloud database. Use JSON backup/restore in the app to transfer records; never put backups or passwords on GitHub. Initial research may take a few minutes. Failed sources are visible in **Settings & sources** and do not prevent manual tracking.

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

## Expanded Canadian research coverage

The October 25 expansion checks a wider set of official Greenhouse and Lever boards for economics, analytics, operations, business systems, pricing, finance, risk, and research. `research_boards.json` registers the additional boards for weekly discovery. The employer watchlist cites current analytical hiring as evidence of a relevant employer to monitor; it does not claim a Summer 2027 internship program. Current Winter 2027 roles and graduate-only research internships are excluded from new Summer results. Stripe’s Data Analyst internship has unclear internship dates despite a specified graduation year; it is not labeled a confirmed Summer 2027 role. Lyft roles require Canadian university enrollment, which is flagged.

Bank, insurer, and several professional-services sites were blocked by cloud network policy during this expansion. Additional required domains have been saved in the environment draft, but their program pages have not been verified and are not added as factual vacancies. No paid research provider is connected.

### Remove an unsuitable posting

Open the posting and click **Delete posting**, then confirm. It disappears from your opportunities, applications, digest and contact links. The removal is saved locally and survives research updates and backup/restore. In the Pages version it applies only to your current browser; it does not delete the shared research catalogue for other visitors. Contacts and their interaction history are retained.

### Recruitment contacts

Each record has a Recruitment Contact field. The detail panel shows contact scope, source evidence, last successful contact verification and failed checks. Contact verification never refreshes the posting's own verification date. Manual corrections through the detail form are labeled as manually entered; browser overrides are preserved through public research updates.

`recruitment_sources.json` defines the company career pages and official boards searched during each weekly run, plus individually reviewed contacts. Verified internship inboxes take priority over a general recruiting inbox; named recruiter fallbacks require a published work email and evidence of their recruiting role. Email addresses are never guessed. Accommodation, privacy, reference-submission and security-reporting addresses are excluded from general internship inquiries. Published recruiting inboxes can still have unconfirmed Canadian/internship scope, which is stated in the detail panel. Inaccessible sources and missing public contacts remain explicit research gaps, not invented contacts.

Francophone Mobility eligibility and employer participation are separate questions. Ask whether the employer can support the pathway, and describe eligibility as confirmed only when it has been verified.
