# Install the App on Your Phone and Use It Daily

This guide covers the main ways to get the app onto your phone and use it every day.

---

## What You Need

- **Backend** running somewhere your phone can reach (your computer on the same Wi‑Fi, or a deployed server).
- **API URL** the app will call (e.g. `http://YOUR_IP:8000` for local, or `https://your-api.example.com` for production).
- **Gemini API key** in `mobile/.env.local` for Live Coach and other AI features.

---

## Option A: Add to Home Screen (Easiest – No Mac Required)

Use the app in the browser, then add it to your home screen so it feels like an app.

### 1. Run backend and app on your computer

```bash
# Terminal 1: start backend
cd /path/to/project_inside/backend
# use your usual command, e.g.:
make dev
# or: poetry run uvicorn app.main:app --reload --host 0.0.0.0
```

```bash
# Terminal 2: start mobile app
cd /path/to/project_inside/mobile
npm install
npm run dev
```

### 2. Point the app at your backend

Create or edit `mobile/.env.local`:

```bash
# Use your computer’s IP so your phone can reach the backend (same Wi‑Fi)
VITE_API_BASE_URL=http://YOUR_COMPUTER_IP:8000
GEMINI_API_KEY=your_gemini_api_key
```

Find your IP:

- **macOS:** System Settings → Wi‑Fi → your network → IP address, or run `ipconfig getifaddr en0`.
- **Windows:** `ipconfig` and use the IPv4 address for your Wi‑Fi adapter.

Restart the dev server after changing `.env.local`.

### 3. Open on your phone

1. Connect your phone to the **same Wi‑Fi** as your computer.
2. On the phone, open Safari (iPhone) or Chrome (Android).
3. Go to: **`http://YOUR_COMPUTER_IP:3000`**  
   (Use the same IP as in `VITE_API_BASE_URL`, port 3000.)

### 4. Add to home screen (use it daily like an app)

- **iPhone:** Safari → Share → **Add to Home Screen** → name it (e.g. “Inside”) → Add.
- **Android:** Chrome → menu (⋮) → **Add to Home screen** or **Install app**.

After that, open the app from the new home screen icon. You still need the backend and dev server running when you use it.

**Limitation:** Your phone must be on the same network as the computer running backend + dev server (or you need a different setup below).

---

## Option B: Native iOS App (iPhone, Mac + Xcode)

Best for “real” app install, push, and offline-capable shell. Requires a Mac and Xcode.

### 1. One-time setup on your Mac

```bash
cd /path/to/project_inside/mobile
npm install
```

Create `mobile/.env.local` with your backend URL and Gemini key (see Option A). For a device on the same Wi‑Fi, use your Mac’s IP:

```bash
VITE_API_BASE_URL=http://YOUR_MAC_IP:8000
GEMINI_API_KEY=your_gemini_api_key
```

Build the web app and sync to iOS:

```bash
npm run build
npx cap sync ios
npx cap open ios
```

### 2. Install on your iPhone

1. Connect the iPhone with a USB cable.
2. In Xcode: select your **Team** (Apple ID), choose your **iPhone** as the run target.
3. Click **Run** (▶). The app installs and launches on the phone.

If you see “Untrusted Developer”: on the phone go to **Settings → General → VPN & Device Management**, tap your developer account, then **Trust**.

### 3. Use it daily

- As long as the backend is running at the URL in `VITE_API_BASE_URL`, open the “Project Inside” app on your phone as usual.
- To update the app after code changes: run `npm run build`, then `npx cap sync ios`, then Run from Xcode again.

---

## Using It Daily: Keeping the Backend Reachable

The app always needs the **backend** to be reachable. Two patterns:

### Same Wi‑Fi (simple)

- Start backend and (for Option A) dev server on your computer.
- Use your computer’s IP in `VITE_API_BASE_URL` and connect the phone to the same Wi‑Fi.
- **Downside:** When the computer sleeps or you’re away from home, the app won’t work unless you use the next approach.

### Backend (and optionally app) on the internet

For use from anywhere (different Wi‑Fi, cellular):

1. **Deploy the backend** to a server (e.g. Railway, Render, Fly.io, a VPS) with a public URL like `https://your-api.example.com`.
2. **Set the app’s API URL to that:**  
   In `mobile/.env.local` use `VITE_API_BASE_URL=https://your-api.example.com`, then rebuild (and for iOS, sync and re-run from Xcode).
3. **Optional:** Deploy the mobile web app (the `mobile` Vite app) to Vercel/Netlify and use that URL on the phone; then “Add to Home Screen” from that URL so you have one stable link and still use the deployed backend.

---

## Deploy to iPhone using DigitalOcean backend

To install the native iOS app on your iPhone and have it use **https://project-inside-c6bdb.ondigitalocean.app** (no local backend):

1. **Set the API URL for the build** (pick one):
   - **Option A:** Copy the production env file and build:
     ```bash
     cd mobile
     cp .env.production.example .env.production
     # .env.production already has VITE_API_BASE_URL=https://project-inside-c6bdb.ondigitalocean.app
     ```
   - **Option B:** In `mobile/.env.local` set:
     ```bash
     VITE_API_BASE_URL=https://project-inside-c6bdb.ondigitalocean.app
     ```
     (Keep `GEMINI_API_KEY` there if you use Live Coach / AI features.)

2. **Build the web app and sync to iOS:**
   ```bash
   cd mobile
   npm install
   npm run build
   npx cap sync ios
   npx cap open ios
   ```

3. **Install on your iPhone:**
   - Connect the iPhone with a USB cable.
   - In Xcode: choose your **Team** (Apple ID), select your **iPhone** as the run target.
   - Click **Run** (▶). The app installs and launches.
   - If you see “Untrusted Developer”: on the phone go to **Settings → General → VPN & Device Management**, tap your developer account, then **Trust**.

The app will call the API at `https://project-inside-c6bdb.ondigitalocean.app/v1/...` and works from anywhere (Wi‑Fi or cellular). To change the URL later, update `VITE_API_BASE_URL`, run `npm run build`, then `npx cap sync ios` and Run from Xcode again.

---

## How do I know if the app uses production or local?

**When each URL is used**

- **`npm run build`** (what gets installed on your iPhone) uses **production** env: `.env.production.local` (if present) > `.env.production` > `.env.local` > `.env`. So if you have `.env.production` with the DigitalOcean URL and no `.env.production.local`, the built app uses **production**.
- **`npm run dev`** (browser on your computer) uses **development** env: `.env.development.local` > `.env.development` > `.env.local` > `.env`. So the dev server usually uses whatever is in `.env.local` (e.g. your local IP).

**Rule of thumb:** The URL is fixed at **build time**. The app on your iPhone uses whatever `VITE_API_BASE_URL` was when you last ran `npm run build`. If you built after setting `.env.production` to the DO URL (or copied from `.env.production.example`), the iPhone app uses production.

**Check on the device:** In the app, open **Profile → Settings**. The **API** line at the top shows the base URL this build is using (e.g. `https://project-inside-c6bdb.ondigitalocean.app` = production, `http://192.168.x.x:8000` = local).

---

## Quick Reference

| Goal                         | Steps |
|-----------------------------|--------|
| Use on phone today (easiest) | Option A: run backend + `npm run dev`, set IP in `.env.local`, open `http://IP:3000` on phone, Add to Home Screen. |
| Install as native iOS app   | Option B: `npm run build` → `npx cap sync ios` → Xcode → Run to device. |
| Use from anywhere daily      | Deploy backend to a public URL, set `VITE_API_BASE_URL` to that URL, rebuild/sync. |

---

## Troubleshooting

- **“Cannot connect to server”**  
  - Phone and backend must be on same network (for local IP), or backend must be deployed and URL correct.  
  - Check `VITE_API_BASE_URL` and that nothing is blocking ports 3000 (app) and 8000 (backend).

- **CORS errors**  
  - Backend must allow your app origin (e.g. `http://YOUR_IP:3000` or your deployed app URL). Configure CORS in the backend and restart.

- **App works in browser but not from home screen**  
  - Same URL must be used. Clear cache or re-add to home screen from the same `http://YOUR_IP:3000` (or your deployed URL).

- **iOS: “Untrusted Developer”**  
  - Settings → General → VPN & Device Management → your developer account → Trust.
