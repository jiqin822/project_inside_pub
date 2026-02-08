# DigitalOcean App Spec — Line-by-Line Explanation

This doc explains each field in a DigitalOcean App Platform app spec. Your repo has two related specs: `.do/app.yaml` (default) and `.do/app-spec-add-web.yaml` (snippets for adding web + ingress).

---

## Top-level app identity

| Line / field | Meaning |
|--------------|--------|
| `name: project-inside` | App name in DigitalOcean. Used in the dashboard and default URL (e.g. `project-inside-xxxx.ondigitalocean.app`). |

---

## Alerts (optional)

```yaml
alerts:
  - rule: DEPLOYMENT_FAILED
  - rule: DOMAIN_FAILED
```

| Field | Meaning |
|-------|--------|
| `alerts` | List of conditions that trigger notifications (email/Slack, etc., if configured). |
| `rule: DEPLOYMENT_FAILED` | Alert when a deployment fails. |
| `rule: DOMAIN_FAILED` | Alert when custom domain verification or TLS fails. |

---

## Static site (frontend) — `static_sites`

A **static site** is a build that produces HTML/JS/CSS; the platform serves the files and does not run a long-lived server.

```yaml
static_sites:
  - name: web
    source_dir: mobile
    build_command: npm run build
    output_dir: dist
    environment_slug: node-js
    index_document: index.html
    catchall_document: index.html
    routes:
      - path: /
    envs:
      - key: VITE_API_BASE_URL
        value: https://project-inside-c6bdb.ondigitalocean.app
```

| Field | Meaning |
|-------|--------|
| `static_sites` | List of static-site components (SPA or static HTML). |
| `name: web` | Component name; used in the dashboard and in `ingress.rules` when you use custom ingress. |
| `source_dir: mobile` | Repo directory that contains the frontend (e.g. `package.json`, `vite.config`). |
| `build_command: npm run build` | Command run in `source_dir` to build the app (produces `dist/` for Vite). |
| `output_dir: dist` | Directory (relative to `source_dir`) that holds the built files to be served. |
| `environment_slug: node-js` | Runtime used for the build (Node.js). |
| `index_document: index.html` | File served for the root path `/`. |
| `catchall_document: index.html` | File served for paths that don’t match a real file (SPA client-side routing). |
| `routes: - path: /` | **Default routing:** this component is served for path prefix `/`. Omit `routes` if you use `ingress.rules` (routing is then defined only in ingress). |
| `envs` | Environment variables for the **build** (and optionally run). |
| `key: VITE_API_BASE_URL` | Vite injects this at build time; frontend uses it as the API base URL. |
| `value: https://...` | Your app’s public URL (no trailing slash). Use `/project-inside-backend` in the path if the API is under that prefix. |
| `scope: RUN_AND_BUILD_TIME` or `BUILD_TIME` | When the var is available; for `VITE_*` you typically use build-time so it’s baked into the bundle. |

**When using `ingress`:** Do **not** set `routes` on the static site; define paths only under `ingress.rules`.

**Optional under static_sites:**

| Field | Meaning |
|-------|--------|
| `github.repo` | GitHub repo (e.g. `owner/repo`). |
| `github.branch` | Branch to deploy (e.g. `main`). |
| `github.deploy_on_push` | Deploy automatically on push to that branch. |

---

## Databases (optional)

```yaml
databases:
  - cluster_name: app-xxxx
    db_name: dev-db-193637
    db_user: dev-db-193637
    engine: PG
    name: dev-db-193637
    production: true
    version: "17"
```

| Field | Meaning |
|-------|--------|
| `databases` | List of managed databases attached to the app. |
| `cluster_name` | ID of the existing database cluster in your DO account. |
| `db_name` | Database name inside the cluster. |
| `db_user` | User name for connections. |
| `engine: PG` | Engine type (PostgreSQL). |
| `name` | Logical name for this DB resource in the app (used to inject `DATABASE_URL` into components). |
| `production` | Whether this is a production DB (affects backups/sizing). |
| `version` | Major engine version (e.g. `"17"`). |

---

## Global env vars — `envs` (top-level)

```yaml
envs:
  - key: VITE_API_BASE_URL
    scope: RUN_AND_BUILD_TIME
    value: https://project-inside-c6bdb.ondigitalocean.app
```

| Field | Meaning |
|-------|--------|
| `envs` (at top level) | Variables applied to **all** components (often overridden per-component). |
| `key` | Environment variable name. |
| `scope` | `RUN_TIME`, `BUILD_TIME`, or `RUN_AND_BUILD_TIME`. |
| `value` | Value (plain text; use **encrypted** / secret in dashboard for secrets). |

---

## Features (optional)

```yaml
features:
  - buildpack-stack=ubuntu-22
```

| Field | Meaning |
|-------|--------|
| `features` | Feature flags / build options. |
| `buildpack-stack=ubuntu-22` | Use Ubuntu 22 base image for buildpack-based builds. |

---

## Ingress — custom routing

When you have both a static site and a service, you can route by path with **ingress** instead of per-component `routes`. Each rule maps a path (and optionally host) to a component.

```yaml
ingress:
  rules:
    - component:
        name: project-inside-backend
      match:
        path:
          prefix: /project-inside-backend
    - component:
        name: web
      match:
        path:
          prefix: /
```

| Field | Meaning |
|-------|--------|
| `ingress` | Custom routing rules (path/host → component). |
| `rules` | List of rules; **order matters** (more specific prefixes should come first). |
| `component.name` | Which component (service or static site) receives the traffic. |
| `match.path.prefix` | URL path prefix (e.g. `/project-inside-backend` for API, `/` for the SPA). |
| `match.authority.exact` | Optional: exact hostname (e.g. custom domain). `""` often means “any”. |

**Important:** No two rules can use the same path prefix. Use `/project-inside-backend` for the API and `/` for the web app to avoid “path prefix / already in use”.

---

## Service (backend) — `services`

A **service** is a long-running process (e.g. FastAPI) that listens on an HTTP port.

```yaml
services:
  - name: project-inside-backend
    source_dir: backend
    build_command: pip install -r requirements.txt
    run_command: uvicorn app.main:app --host 0.0.0.0 --port 8080
    environment_slug: python
    http_port: 8080
    instance_count: 1
    instance_size_slug: apps-s-1vcpu-2gb
    routes:
      - path: /v1
    preserve_path_prefix: true
```

| Field | Meaning |
|-------|--------|
| `services` | List of app services (backends). |
| `name: project-inside-backend` | Component name; must match `ingress.rules[].component.name` if you use ingress. |
| `source_dir: backend` | Repo directory for the backend (e.g. where `requirements.txt` and `app/` live). Use `/backend` if the spec is at repo root. |
| `build_command` | Command run in `source_dir` to install dependencies (e.g. `pip install -r requirements.txt`). |
| `run_command` | Command that starts the app (e.g. `uvicorn app.main:app --host 0.0.0.0 --port 8080`). |
| `environment_slug: python` | Runtime (Python buildpack). |
| `http_port: 8080` | Port the process listens on; platform routes traffic to this port. |
| `instance_count: 1` | Number of instances (replicas). |
| `instance_size_slug` | Droplet size (e.g. `apps-s-1vcpu-2gb`). |
| `routes: - path: /v1` | **Default routing:** this component gets requests whose path starts with `/v1`. Omit if using `ingress.rules`. |
| `preserve_path_prefix: true` | Forward the path prefix to the app (e.g. `/v1/...` or `/project-inside-backend/...`) instead of stripping it. |

**Service env vars:** Under the same service you add `envs:` with `key`, `scope`, and `value` (e.g. `DATABASE_URL`, `CORS_ORIGINS`, API keys). Use the dashboard “encrypted” option for secrets.

---

## Region

```yaml
region: nyc
```

| Field | Meaning |
|-------|--------|
| `region` | Data center region (e.g. `nyc`, `sfo`, `ams`). |

---

## Quick reference: routing

- **Without ingress:** Each component has its own `routes` (e.g. static site `path: /`, service `path: /v1`).
- **With ingress:** Do **not** set `routes` on components; define all path rules under `ingress.rules` with different path prefixes (e.g. backend `/project-inside-backend`, web `/`).

For more, see [DigitalOcean App Platform spec](https://docs.digitalocean.com/products/app-platform/reference/app-spec/).
