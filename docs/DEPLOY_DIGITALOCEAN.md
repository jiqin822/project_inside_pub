# Deploying to DigitalOcean App Platform

This repo is a **monorepo**: the app is not at the root. DigitalOcean scans the root and finds no `package.json` or `requirements.txt`, so you get "No components detected" unless you use the app spec or set source directories.

## Do backend and frontend need to be deployed separately?

**No.** You deploy **one app** with **two components** (same repo, same app):

1. **Static site (web)** – frontend in `mobile/`, built with Node, served at `/`.
2. **Service (api)** – backend in `backend/`, Python/FastAPI, served at `/v1`.

The `.do/app.yaml` in this repo defines both. One push deploys both; you don’t create two separate apps. They share one domain; DigitalOcean may run the two components on different containers behind the same ingress.

## Can both run on the same server (one component)?

**Yes.** If you want a single service (one container) serving both the API and the frontend:

1. **Build:** In the service build step, build the frontend first (e.g. `cd mobile && npm ci && npm run build`), then copy `mobile/dist` into a directory the backend can serve (e.g. `backend/static_web`), then run `pip install -r requirements.txt`.
2. **Run:** The backend mounts that directory at `/` (and keeps `/v1` for the API) and runs as usual.

That way you have one App Platform **service** (one “server”) instead of one static site + one service. The repo’s default `.do/app.yaml` uses two components (static site + api) for simplicity and separate scaling; if you prefer one component, you’d use a custom app spec with a single service and a multi-step build that produces both the frontend assets and the backend, and you’d add the static mount in the FastAPI app (see `FastAPI` docs for serving static files and SPA fallback).

## Option 1: Use the app spec (recommended)

The repo includes `.do/app.yaml`, which defines:

**Static site `web`:**
- **Source directory:** `mobile`
- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Environment:** Node.js
- **Routes:** `/` → static site

**Service `api`:**
- **Source directory:** `backend`
- **Build command:** `pip install -r requirements.txt`
- **Run command:** `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- **Environment:** Python
- **HTTP port:** 8080
- **Routes:** `/v1` → backend (path prefix preserved)
- **Python version:** `backend/runtime.txt` and `backend/.python-version` pin **Python 3.12** so the buildpack does not use 3.13 (asyncpg/pydantic wheels are not yet compatible with 3.13).
- **Single package manager:** Only `backend/requirements.txt` is used for the cloud build; `backend/poetry.lock` is removed and ignored so the buildpack does not see both Poetry and pip.
- **Start command:** `backend/Procfile` defines the `web` process so the platform can launch the API (uvicorn on 0.0.0.0:8080).

When you create an app from this repo:

1. In the DigitalOcean App Platform create flow, connect your GitHub repo and branch.
2. Use the **existing app spec** so it loads `.do/app.yaml` (both components will be created).
3. Add a **Postgres** database (and Redis if needed) in the DO app, then set env vars on the **api** component: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, etc. (see `backend/.env.example`).
4. Set **VITE_API_BASE_URL** on the **web** component (build-time) to your app’s URL so the frontend calls the correct API (e.g. `https://your-app.ondigitalocean.app`).

**Quick env config** (replace `YOUR_APP` with your app subdomain):

| Where | Env var | Value |
|-------|---------|--------|
| **Web** (static site) | `VITE_API_BASE_URL` | `https://YOUR_APP.ondigitalocean.app` (no trailing slash) |
| **Api** (service) | `CORS_ORIGINS` | `["https://YOUR_APP.ondigitalocean.app"]` |
| **Api** | `APP_PUBLIC_URL` | Same URL (for emails/links) |
| **Api** | `DATABASE_SSL_VERIFY` | optional; default is `false` (skip verify for managed Postgres). Set `true` for strict verification. |

**This app:** `https://project-inside-c6bdb.ondigitalocean.app/`

- **Web:** `VITE_API_BASE_URL=https://project-inside-c6bdb.ondigitalocean.app` (no trailing slash)
- **Api:** `CORS_ORIGINS=["https://project-inside-c6bdb.ondigitalocean.app"]`, `APP_PUBLIC_URL=https://project-inside-c6bdb.ondigitalocean.app`

**Static ingress IPs** (e.g. 162.159.140.98, 172.66.0.96): add these to your **database Trusted Sources** (and any service that IP-allowlists your app). Do not put IPs in the frontend or CORS.

### Google Application Default Credentials (Speech-to-Text)

Live Coach uses **Google Cloud Speech-to-Text**. On DigitalOcean you cannot upload a key file, so use **inline JSON**:

1. **Create a GCP service account** (if you don’t have one):
   - [Google Cloud Console](https://console.cloud.google.com/) → **IAM & Admin** → **Service Accounts** → **Create Service Account**.
   - Name it (e.g. `project-inside-stt`), optionally add a description.
   - **Create and Continue** → under **Grant this service account access**, add role **Cloud Speech-to-Text User** (and **Storage Object Viewer** if you use custom recognizers).
   - **Done**.

2. **Create a JSON key**:
   - Open the service account → **Keys** → **Add Key** → **Create new key** → **JSON** → **Create**. A `.json` file downloads.

3. **Set env on the api component**:
   - Open your app → **api** component → **Settings** → **Environment Variables**.
   - Add a **secret** (encrypted) variable:
     - **Key:** `GOOGLE_APPLICATION_CREDENTIALS_JSON`
     - **Value:** the **entire contents** of the JSON file (one line, or paste as-is; the app accepts raw JSON or base64-encoded JSON).
   - DigitalOcean encrypts secret env vars; do **not** use `GOOGLE_APPLICATION_CREDENTIALS` (file path) on App Platform—there is no persistent file system.

4. **Set STT recognizer** (api component env):
   - **Key:** `STT_RECOGNIZER`
   - **Value:** e.g. `projects/YOUR_GCP_PROJECT_ID/locations/global/recognizers/_` (replace `YOUR_GCP_PROJECT_ID` with the project ID from the JSON key’s `project_id` field).

At startup the backend writes `GOOGLE_APPLICATION_CREDENTIALS_JSON` to a temp file and sets `GOOGLE_APPLICATION_CREDENTIALS` so Google clients (Speech-to-Text, optional Firebase) work. If `GOOGLE_APPLICATION_CREDENTIALS` is already set (e.g. local path), the inline JSON step is skipped.

#### If "Service account key creation is disabled" (Organization Policy)

Your GCP organization may enforce **iam.disableServiceAccountKeyCreation**, so you cannot create or download JSON keys for service accounts. In that case:

1. **Request an exception (recommended if you need keys on DigitalOcean)**  
   An **Organization Policy Administrator** (`roles/orgpolicy.policyAdmin`) can:
   - In [Google Cloud Console](https://console.cloud.google.com/) → **IAM & Admin** → **Organization Policies**, find **Disable service account key creation** (`iam.disableServiceAccountKeyCreation`).
   - **Manage policy** → add an **exception** for your **project** (or a folder) so that service account keys are allowed for that scope.  
   Then create the JSON key as in steps 1–2 above and use `GOOGLE_APPLICATION_CREDENTIALS_JSON` on the api component.

2. **Run the backend on GCP instead of DigitalOcean**  
   On **Google Cloud Run** (or GCE, GKE), the app can use the **metadata server** for Application Default Credentials—no service account key file is needed. Deploy the same backend to Cloud Run, attach a service account to the service, and grant it **Cloud Speech-to-Text User**. ADC will work without any key. This avoids keys entirely and is often preferred when your org disallows key creation.

3. **Workload Identity Federation (advanced)**  
   If you must stay on DigitalOcean and cannot get a key or exception, you would need to set up [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation) with an OIDC provider that your deployment can use. DigitalOcean App Platform does not expose OIDC tokens for app workloads in a standard way, so this path usually requires a custom proxy or moving the STT-calling part to a GCP service.

4. **Use a different Speech-to-Text provider**  
   As a fallback, you could replace Google Speech-to-Text with another provider (e.g. AWS Transcribe, AssemblyAI, Deepgram) and adapt the backend STT routes to use that API. This requires code changes and does not use GCP credentials.

### Phone app: "Load failed" on login/register

If the server is healthy but the phone app can’t log in or register:

1. **CORS:** On the **api** component, set **CORS_ORIGINS** to include your app URL: `["https://YOUR_APP.ondigitalocean.app"]` (no trailing slash). The backend also allows `capacitor://localhost` and `ionic://localhost` for native apps.
2. **API URL:** The frontend must call your backend. If you open the **web app** in the phone browser, the DO-built frontend already has the right URL. If you use a **native** (Capacitor) app, build it with **VITE_API_BASE_URL** set to `https://YOUR_APP.ondigitalocean.app` (see `mobile/INSTALL_ON_PHONE.md`).
3. **Check:** In the app, open **Profile → Settings** and confirm the displayed API URL is your backend (e.g. `https://...ondigitalocean.app`). If it shows `http://localhost:8000`, the app was built without the production API URL.

If you already created an app and it failed with "No components detected":

1. Open your app → **Edit your app spec** and paste/use the contents of `.do/app.yaml`, or add two components manually (static site from `mobile/`, service from `backend/`) with the settings above.

### Remote site (web) still not deployed

If the backend deploys but the **web (frontend) site** does not appear or does not update after a push:

1. **Confirm the web component exists**  
   In DigitalOcean: **Apps** → your app → check that you have **two** components (e.g. **web** and **api** or **project-inside-backend**). If only the API exists, add the static site: **Edit your app spec** and ensure a `static_sites:` entry is present (see `.do/app.yaml` or `.do/app-full.yaml`), then save. Or add a component manually: **Add Component** → **Static Site**, source directory `mobile`, build `npm run build`, output `dist`.

2. **Which spec is in use**  
   If the app was created from the repo, it may use **App Spec** from a file (e.g. `.do/app.yaml`). The default `.do/app.yaml` includes both `web` and `api`. If you use the full spec (e.g. `.do/app-full.yaml`), ensure the file is the one selected in **Settings** → **App Spec** and that it contains the `static_sites` block with `name: web`, `source_dir: mobile`, and (if you use ingress) that `ingress.rules` has a rule for `component.name: web` with `path.prefix: /`.

3. **Trigger a deploy for the web component**  
   - **Deploy on push:** In the **web** component → **Settings** → **Source**, confirm **Deploy on push** is enabled and the **branch** (e.g. `main`) matches the branch you push to.  
   - **Manual deploy:** **Apps** → your app → **Deploy** dropdown → **Deploy Branch** (or **Deploy Latest Commit**) so both components build.  
   - If the app is connected to a **fork**, ensure the connected repo and branch are the one you push to; otherwise pushes won’t trigger a deploy.

4. **Check the last web build**  
   Open the **web** component → **Runtime Logs** / **Build Logs** (or the latest deployment). If the last deployment only shows the **api** build, the web component may not have been included in that deployment—trigger a new deploy. If the **web** build failed, fix the error (e.g. Node version, missing env like `VITE_API_BASE_URL`, or build script failure).

5. **URL and routing**  
   - Default setup (`.do/app.yaml`): frontend at `https://YOUR_APP.ondigitalocean.app/`, API at `.../v1`.  
   - With ingress (`.do/app-full.yaml`): frontend at `https://YOUR_APP.ondigitalocean.app/`, API at `.../project-inside-backend`.  
   Ensure **VITE_API_BASE_URL** on the web component (build-time) matches how you reach the API (same host; with ingress use `.../project-inside-backend`).

After changing the app spec (e.g. adding the static site), **save** and run a new deployment so the web component is built and deployed.

## Option 2: Set source directories manually (no spec)

If you’re not using the spec:

1. **Frontend:** Add a static site component; set **Source Directory** to `mobile`, **Build Command** to `npm run build`, **Output Directory** to `dist`.
2. **Backend:** Add a service component; set **Source Directory** to `backend`, **Build Command** to `pip install -r requirements.txt`, **Run Command** to `uvicorn app.main:app --host 0.0.0.0 --port 8080`, **HTTP Port** to `8080`, and route path `/v1` with path prefix preserved.

---

## How the database is handled on DigitalOcean

The backend needs **PostgreSQL** (and optionally **Redis**). You can do either of the following.

### Option A: Managed Database in the same app (recommended)

1. **Create a PostgreSQL cluster** (if you don’t have one):
   - In the DigitalOcean control panel: **Create** → **Databases** → **PostgreSQL**, choose region/plan, create.
   - Or add a **database component** in your App Platform app (your app → **Settings** → **App Spec** → add a `databases:` entry, or use **Add Resource** → **Database** in the UI).

2. **Attach it to the app**:
   - In your app: **Resources** or **Add Resource** → **Create or attach database** → **Attach existing DigitalOcean database** (or create a dev database from the app).
   - Select the cluster (and database name / user if prompted).

3. **Connect the API component**:
   - Open the **api** component → **Settings** → **Environment Variables**.
   - Add **DATABASE_URL**: use the **bindable** value provided by App Platform for the attached database (e.g. `$db.DATABASE_URL` or the exact variable name shown when you attach the DB).
   - The backend uses **asyncpg**. If DO gives a `postgresql://` URL, change it to **`postgresql+asyncpg://`** in the same host/path (e.g. `postgresql+asyncpg://user:pass@host:25060/defaultdb?sslmode=require`).

4. **Redis (optional):** If your app uses Redis, create a Redis cluster (Create → Databases → Redis), attach it to the app, and set **REDIS_URL** (and **REDIS_QUEUE_URL** if used) on the **api** component to the bound connection string.

### Option B: External database

- Use a PostgreSQL host outside DO (e.g. Supabase, Neon, or your own server).
- Set **DATABASE_URL** on the **api** component to your connection string (must be **`postgresql+asyncpg://...`** for this backend).
- Set **REDIS_URL** (and **REDIS_QUEUE_URL** if needed) if you use an external Redis.

### Migrations

After the database is attached and **DATABASE_URL** is set, run migrations from your machine (or a one-off job) against that URL:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://user:pass@your-db-host:25060/defaultdb?sslmode=require" alembic upgrade head
```

Or add a **job** component in the app spec that runs `alembic upgrade head` once at deploy time (same **DATABASE_URL** as the api component).

### "relation \"users\" does not exist" (UndefinedTableError)

If the **API** logs show:

```text
asyncpg.exceptions.UndefinedTableError: relation "users" does not exist
```

the remote database has no tables yet. **Migrations have not been run** against the database the API is using.

**Fix:** Run Alembic migrations against the **same** `DATABASE_URL` the api component uses:

1. **Get the connection string** from DigitalOcean: App → **api** component → **Settings** → **Environment Variables** → copy `DATABASE_URL` (or the bound variable, e.g. `$db.DATABASE_URL`). Ensure it uses the asyncpg driver: `postgresql+asyncpg://...` (the backend normalizes `postgresql://` to `postgresql+asyncpg://` when you run from your machine, but the URL must point to the **remote** DB).

2. **From your machine** (with network access to the DB: add your IP to the database **Trusted Sources** in DO, or use `0.0.0.0/0` for testing):

   ```bash
   cd backend
   export DATABASE_URL="postgresql+asyncpg://user:pass@your-db-host:25060/defaultdb?sslmode=require"
   # If your Mac can't verify the DB cert:
   export DATABASE_SSL_VERIFY=false
   alembic upgrade head
   ```

3. **Redeploy** is not required; the next request will use the new tables. Then try login/signup again.

To seed demo users after migrations, see **Inject demo family to remote server** below.

### "Permission denied for schema public"

PostgreSQL 15+ (and DigitalOcean managed Postgres) often do **not** grant new users the right to create objects in the `public` schema. If migrations or seed fail with:

```text
asyncpg.exceptions.InsufficientPrivilegeError: permission denied for schema public
```

you must grant your **app database user** access to `public` **before** running `alembic upgrade head`. Use a user that has admin/superuser rights (e.g. the **default/admin** user from the DigitalOcean database dashboard).

**Quick fix (DigitalOcean):**

1. In DigitalOcean you need **two** connection strings:
   - **App:** the one you were given (e.g. username **dev-db-193637**, database **dev-db-193637**) — this is your api `DATABASE_URL`; the app user cannot grant schema rights to itself.
   - **Admin:** the cluster’s default user **doadmin**. To get it: go to **Databases** (left sidebar) → click your **PostgreSQL cluster** (not the app) → **Users & Databases**. You should see a default user **doadmin**; use **Reset password** or **Show** to get its password. Use **doadmin** + that password in the grant step (with database name **dev-db-193637** in the URL, not defaultdb).
2. Add your machine’s IP to the database **Trusted Sources** (cluster → **Settings** or **Trusted sources**).
3. From your machine (in `backend/`), grant schema rights **once** using the **admin** URL. **Use the same database name as your app** (e.g. `dev-db-193637` in the path), not `defaultdb`, or the grants apply to the wrong database and migrations will still fail:

   ```bash
   export DATABASE_URL='postgresql://doadmin:YOUR_ADMIN_PASSWORD@YOUR_DB_HOST:25060/dev-db-193637?sslmode=require'
   export TARGET_USER='dev-db-193637'   # replace with your app DB username from api DATABASE_URL
   export DATABASE_SSL_VERIFY=false
   bash scripts/grant_schema_public.sh
   ```

4. Then run migrations using the **app** connection string (the one from your api component):

   ```bash
   export DATABASE_URL='postgresql://dev-db-193637:APP_PASSWORD@YOUR_DB_HOST:25060/dev-db-193637?sslmode=require'
   export DATABASE_SSL_VERIFY=false
   alembic upgrade head
   ```

Then run seed if needed (`bash scripts/seed_remote_demo_family.sh`).

**Manual option (same idea):**

1. Connect to the database as that admin user (e.g. via `psql`, or DO’s “Connection parameters” / “Connection string” for the admin user).
2. Run (replace `your_app_user` with the actual DB user name, e.g. `dev-db-193637`):

   ```sql
   GRANT ALL ON SCHEMA public TO your_app_user;
   GRANT CREATE ON SCHEMA public TO your_app_user;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO your_app_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO your_app_user;
   ```

3. Re-run migrations and seed from your machine (or redeploy).

**Where to find the cluster (and doadmin).** Your database may be **attached to your App**, not listed under the top-level **Databases** menu:

- **Via App (most likely):** **Apps** (left sidebar) → your app (e.g. project-inside) → **Resources** (or the tab where components are listed). Find the **database** resource and click it. Look for **Manage**, **Open in Databases**, **Connection details**, or **Users & databases** — that should take you to the cluster’s page, where you’ll see **Users & Databases** and the **doadmin** user (use **Reset password** or **Show** to get its password).
- **Via Databases:** **Databases** (left sidebar) → if you see a **list of clusters**, click your PostgreSQL cluster (e.g. db-postgresql-…) → **Users & Databases**. If **Databases** shows an empty list or no cluster, use the App path above.

**I only see one user (dev-db-193637).** The credentials you were given are the **app** user. The cluster has a default **doadmin** user; get to the cluster via App → Resources → database (see above), then **Users & Databases** → **doadmin** → **Reset password** or **Show**. If you truly don’t see **doadmin**, check **Connection parameters** for a second connection string, or contact DigitalOcean support; the app user cannot grant itself schema rights.

**App Platform dev database.** If your database is an **App Platform dev database** (created with the app, not a standalone Managed Database), it does not appear in **Databases** or `doctl databases list`, and **doadmin** is typically not exposed. To fix "permission denied for schema public", **contact DigitalOcean support** and ask them to run the GRANT statements for your app database user (e.g. `dev-db-193637`) on schema `public` in that database. Paste the SQL from the "Manual option" above (the six `GRANT` / `ALTER DEFAULT PRIVILEGES` statements with your username). Once support has run them, run `alembic upgrade head` and `bash scripts/seed_remote_demo_family.sh` from your machine using your app `DATABASE_URL`.

**Can't find Apps list, cluster, or doadmin in the UI.** The control panel loads content with JavaScript; wait for the page to finish loading after you click **Apps** or **Databases**.

- **Direct URLs:** Open **https://cloud.digitalocean.com/apps** (apps list) or **https://cloud.digitalocean.com/databases** (database clusters). If you see an empty list, confirm you're in the correct team/account and try a hard refresh.
- **Via CLI (doctl):** If you have a [DigitalOcean API token](https://docs.digitalocean.com/reference/api/create-personal-access-token/), install [doctl](https://docs.digitalocean.com/reference/doctl/how-to/install/) and run: `doctl auth init` (paste token), then `doctl databases list` to see clusters and `doctl databases get <cluster-id>` for connection info. You can also list apps with `doctl apps list` and get app resources to find the linked database cluster ID.
- **Contact support:** If you still can't get **doadmin** or reach the cluster, open a ticket with DigitalOcean support and ask them to either (1) run the GRANT statements for user `dev-db-193637` on schema `public` in your database, or (2) provide the **doadmin** connection details for that cluster. The GRANTs to run are in the "Manual option" above.

**Script:** From `backend/`, run `./scripts/grant_schema_public.sh` (or `python scripts/grant_schema_public.py`) with **DATABASE_URL** set to the **admin** connection string and **TARGET_USER** set to the app user (e.g. `dev-db-193637`). See the script header for usage.

**Grant ran OK but migrations still fail?** The admin URL must use the **same database name** as the app (the path after the port, e.g. `/dev-db-193637`). If you used `/defaultdb`, the grants were applied in the wrong database. Run the grant script again with the admin URL pointing at the app’s database (e.g. `.../dev-db-193637?sslmode=require`).

**Running from inside the app container?** The container’s `DATABASE_URL` is the **app** user, so the grant script would run as the app user and not have permission to grant. Use **ADMIN_DATABASE_URL** for the grant run only (leave `DATABASE_URL` as-is):  
`ADMIN_DATABASE_URL='postgresql://doadmin:ADMIN_PASS@host:25060/dev-db-193637?sslmode=require' TARGET_USER='dev-db-193637' ./scripts/grant_schema_public.sh`  
Use the same database name in the URL as your app (e.g. `dev-db-193637`).

### SSL certificate verify failed (server)

If the **API** logs show:

```text
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

the app is connecting to the database with SSL verification enabled, and the managed Postgres certificate chain is not trusted by Python’s default SSL context (common with DigitalOcean and similar managed DBs).

**Fix:** The backend **defaults to skipping** certificate verification when using SSL (`sslmode=require`), so a **redeploy** with the latest code should resolve this. No env var is required. If you still see the error, ensure the api component has been redeployed after pulling the latest `main`. Optionally you can set `DATABASE_SSL_VERIFY=false` explicitly. To enable strict certificate verification (e.g. when your DB uses a trusted CA), set `DATABASE_SSL_VERIFY=true`.

### Inject demo family to remote server

To seed the Rivera demo family (Marcus, Priya, Sam) on the **remote** database so you can log in from the app:

**If you run the seed script from inside the app container** (e.g. DigitalOcean “Run command” or console), the **app** database user must already have been granted schema public rights; otherwise migrations fail with `permission denied for schema public`. Do the **“Permission denied for schema public”** steps first (from your machine, as admin), then run the script. Prefer running the script **from your machine** so you can use the same DATABASE_URL and avoid permission issues if the app user has no schema rights yet.

1. **Get the remote `DATABASE_URL`** from DigitalOcean: App → your app → **api** component → **Settings** → **Environment Variables**, or from the database component’s connection string. Use the same URL the API uses (e.g. `postgresql://...`; the backend normalizes it to `postgresql+asyncpg://`).

2. **Allow your machine to reach the DB:** Database → **Settings** → **Trusted Sources** → add your IP or `0.0.0.0/0` for testing.

3. **From your machine** (one-time, or use the script below):

   ```bash
   cd backend
   export DATABASE_URL="postgresql://user:pass@your-db-host:25060/defaultdb?sslmode=require"

   # Migrations (if not already run)
   alembic upgrade head

   # Love Map prompts (required for demo family Love Map data)
   python scripts/seed_love_map_prompts.py

   # Demo family (3 users, family relationship, Love Map, market, etc.)
   python scripts/seed_demo_family.py
   ```

   If a demo user already exists, run `python scripts/cleanup_demo_family.py` first, then `seed_demo_family.py` again.

4. **Log in from the app** using the credentials in **docs/FAMILY_DEMO_CREDENTIALS.md** (e.g. `marcus.rivera@demo.inside.app` / `DemoFamily2025!`).

**Optional script:** From `backend/`, run:

```bash
DATABASE_URL="postgresql://..." ./scripts/seed_remote_demo_family.sh
```

This runs migrations, `seed_love_map_prompts`, and `seed_demo_family` in order (see script for details).
