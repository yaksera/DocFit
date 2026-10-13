# DocFit

Shrink scanned documents, phone photos and PDFs under any upload limit (4 MB, 1 MB, 500 KB…) **while keeping text sharp**. Built for education consultancies in Nepal, whose staff fight university and visa portal upload limits every day.

Example from the test suite: a 4-page, 300 dpi colour scan of **104 MB → 528 KB** (under a 700 KB limit) with text quality rated *excellent*; a phone photo of a document **3.8 MB → 135 KB**, auto-cropped with the shadow removed.

## Why the output looks better than free tools

Free compressors squeeze the whole page as one JPEG, so text blurs first. DocFit uses **mixed raster content (MRC)**, the method professional scanners use:

| Layer | What it holds | Compression |
|---|---|---|
| Text mask | Letters, lines, stamps (shape) | 1-bit, high resolution, CCITT G4 |
| Text colour | Ink colour (blue pen, red stamp) | tiny low-res JPEG |
| Background | Paper, cleaned and whitened | low-res JPEG |
| Photos | Passport photos, ID pictures | separate JPEG at photo resolution |

Plus:
- **Target-size search.** A 9-step quality ladder is binary-searched so the file lands just under the limit at the best quality that fits. Big documents are estimated from sample pages first.
- **Page understanding.** Photo regions vs text, colour vs grey, scanned vs digital pages. Digital PDFs (bank statements) keep their real, selectable text; only their images are recompressed.
- **Phone photo clean-up.** Auto-crop of the paper from the table, shadow and yellow-tint removal (smooth lighting model), white paper.
- **Low-res scans.** 150 dpi scans get a 2× upscaled text layer, so letters come out smooth instead of jagged.
- **Honesty.** If the limit can't be met with readable text, the user is told, with suggestions.

## Product features

- Consultancy accounts with team members (invite links you can share on WhatsApp; no mail server needed), owner/admin/member roles
- Upload many files at once, or **merge** into one PDF in a chosen order; JPG output (ZIP for multi-page)
- Password-protected PDFs (bank statements): unlock, compress, output a normal PDF; the password is erased after use
- Live progress, **before/after comparison** with synced zoom, "compress again at another size" (doesn't count as a new document)
- Tag by student name, search, batch download as ZIP
- **Privacy:** files stored privately and auto-deleted after the plan's retention time (1 h on Free)
- Plans and monthly quotas, **Khalti** payments (monthly / yearly), Django admin for staff
- REST API with API keys (Pro plan) for consultancy CRMs
- Password reset by email

## Project layout

```
backend/
  engine/      compression engine (pure Python, no Django): CLI + library
  accounts/    users, organizations, invites, API keys
  billing/     plans, payments, Khalti
  jobs/        upload/processing/download API, Celery tasks, cleanup
  tests/       engine + API tests (synthetic scans, phone photos, statements)
frontend/      React + TypeScript + Tailwind (Vite)
deploy/        Caddyfile
Dockerfile, docker-compose.yml
```

## Run locally (Windows / macOS / Linux)

Requirements: Python 3.12+ and Node 20+. Redis is **not** required locally; jobs run in a background thread.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env      # then set DEBUG=1 and SITE_URL=http://localhost:8000
python manage.py migrate
python manage.py seed_demo      # demo@docfit.local, password in .env.example (DEMO_PASSWORD)
python manage.py createsuperuser
python manage.py runserver
```

Frontend, either:
- `cd frontend && npm install && npm run build`, then open http://localhost:8000 (Django serves the built app), or
- `npm run dev` for hot reload on http://localhost:5173 (proxies `/api` to port 8000).

Admin: http://localhost:8000/admin (plans and prices are editable there).

### Tests

```bash
cd backend
pytest            # 30 tests: engine quality/size checks + full API flows
```

### Command-line engine

```bash
python -m engine scan.pdf -t 4MB
python -m engine photo1.jpg photo2.jpg marksheet.pdf -t 1MB -o merged     # merge into one PDF
python -m engine statement.pdf -t 500KB --password 1234
python -m engine passport.jpg -t 200KB -f jpg
```

## Deploy (any VPS, e.g. 2 vCPU / 4 GB)

1. Point your domain's DNS A record to the server and install Docker.
2. `cp .env.example .env`, then set `SECRET_KEY`, `SITE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DOMAIN`, `POSTGRES_PASSWORD` and the email settings.
3. `docker compose up -d --build`. Caddy obtains the HTTPS certificate automatically.
4. `docker compose exec web python manage.py createsuperuser`

Services: `web` (gunicorn), `worker` (Celery, runs compressions), `beat` (deletes expired files every 10 min), `db` (PostgreSQL), `redis`, `caddy`. Scale compression with `WORKER_CONCURRENCY` and `DOCFIT_THREADS`.

### Khalti payments

1. Get a merchant account at https://admin.khalti.com and copy the **live secret key** (use the sandbox key with `KHALTI_BASE_URL=https://dev.khalti.com/api/v2/` first).
2. Set `KHALTI_SECRET_KEY` (and `KHALTI_BASE_URL=https://khalti.com/api/v2/` for live).
3. Payments are verified server-side with Khalti's lookup API before a plan is activated; the amount is checked too.

Without a key, the billing page tells customers to contact you, and staff can set plans in the admin.

## API

Authenticate with `Authorization: Bearer dfk_…` (create keys under **API keys** in the app).

| Method | Path | Notes |
|---|---|---|
| POST | `/api/jobs` | multipart `files` (one or more), `target` (`4MB`, `500KB`) or `target_kb`, `color_mode` (`auto`/`color`/`gray`/`bw`), `output_format` (`pdf`/`jpg`), `merge`, `clean_background`, `label`, `password` |
| GET | `/api/jobs/{id}` | `status`, `progress`, `output_bytes`, `met_target`, `text_quality`, `warnings` |
| GET | `/api/jobs/{id}/download` | the result file |
| POST | `/api/jobs/{id}/retry` | new `target_kb` / `color_mode` / `password` |
| GET | `/api/jobs?q=&status=` | paginated list |

## Known limits and next steps

- **Perspective correction** for skewed phone photos (the crop is axis-aligned today). OpenCV would add this.
- **JBIG2** text layer (about 2× smaller than CCITT G4) needs the `jbig2enc` binary; it plugs into `engine/raster.py`.
- **eSewa** payments alongside Khalti.
- OCR text layer for scanned PDFs (searchable output), e.g. via Tesseract.
- Plan prices in the seed migration are placeholders; set your real prices in the admin.
