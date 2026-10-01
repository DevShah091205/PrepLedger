# PrepLedger

A placement and interview preparation tracker. It keeps three records in one place:

- **Applications** – every company you are chasing, the stage it is at, CTC, and the next date that matters.
- **Practice log** – problems you have solved, with a recall rating. A spaced-repetition schedule (1, 3, 7, 14 or 30 days) tells you what to revisit today.
- **Mock tests** – aptitude, coding and interview scores plotted over time.

The overview page shows your pipeline, what is coming up, your review queue, topic coverage and a 12-week activity map.

## Tech
Python 3.12 · FastAPI · SQLite · vanilla JavaScript (no build step, no external CDN) · JWT auth with PBKDF2 password hashing · Docker + Caddy · pytest · GitHub Actions · AWS EC2 + S3 backups.

## Run it in VS Code

1. Install **Python 3.12** (python.org or `brew install python@3.12`) and the **Python** extension for VS Code.
2. **File → Open Folder…** and choose the `prepledger` folder. Open a terminal with **Ctrl + `**.
3. Create the environment and install:

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
4. Start the server:

   ```bash
   python -m uvicorn app.main:app --reload --reload-dir app
   ```
   (or press **F5** and pick *PrepLedger (FastAPI)*)
5. Open **http://localhost:8000** and sign in with the demo account below. (A brand-new account starts empty; its overview offers a **Fill with sample data** button.)

Run the tests with `python -m pytest -q` (expect `7 passed`).

## Demo account (already loaded)
The zip ships with a ready-made account so you can see everything straight away:

| | |
|---|---|
| Email | `dev.shah@prepledger.local` |
| Password | `DevShah@2026` |

It holds 12 company applications at different stages, 33 practice problems (with a review queue), 10 mock scores and a 9-day streak. Dates are relative to the day it was created. To refresh them or restore the account, run `python seed.py` (on AWS: `docker compose exec web python seed.py`). To use your own account instead, register a new one and, if you like, delete the demo data from the Export panel.

Your data lives in `data/prepledger.db`. Delete that file to reset everything.

## Settings
Copy `.env.example` to `.env` for Docker/AWS. Locally the defaults work. `TZ_OFFSET_MINUTES` (default 330, India) decides when "today" rolls over.

## Deploy to AWS
Follow [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md).

## API (all under `/api`, JWT bearer token except register/login)
| | |
|---|---|
| `POST /register`, `/login` | account |
| `GET/POST /applications`, `PUT/DELETE /applications/{id}`, `PATCH /applications/{id}/status` | pipeline |
| `GET/POST /problems`, `PUT/DELETE /problems/{id}`, `POST /problems/{id}/review` | practice log |
| `GET/POST /mocks`, `DELETE /mocks/{id}` | mock scores |
| `GET /dashboard` | everything the overview needs |
| `GET /export/{applications\|problems\|mocks}.csv` | CSV download (formula-injection safe) |

Interactive docs at `/docs`.

## Layout
```
app/main.py        routes, validation, dashboard maths
app/auth.py        password hashing + JWT
app/db.py          SQLite schema
app/static/        index.html, style.css, app.js
tests/             pytest suite
deploy/            Caddyfile, S3 backup script
docs/              AWS deployment guide
```
