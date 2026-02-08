# Deploying Mobile App to iPhone

The mobile app is a TypeScript/React web application. Here are several ways to deploy it to iPhone:

## Option 1: Access via Mobile Browser (Simplest)

### Steps:
1. **Start the development server:**
   ```bash
   cd mobile
   npm run dev
   ```

2. **Find your computer's IP address:**
   ```bash
   # macOS/Linux
   ifconfig | grep "inet " | grep -v 127.0.0.1
   
   # Or use the check_server.sh script
   cd .. && ./check_server.sh
   ```

3. **Update `.env.local`** to use your computer's IP:
   ```bash
   VITE_API_BASE_URL=http://YOUR_IP:8000
   ```

4. **Access on iPhone:**
   - Make sure iPhone is on the same Wi-Fi network
   - Open Safari on iPhone
   - Navigate to: `http://YOUR_IP:3000`

### Pros:
- ✅ No build required
- ✅ Easy to test
- ✅ Hot reload works

### Cons:
- ❌ Requires same network
- ❌ Not installable as an app
- ❌ URL bar visible

---

## Option 2: Progressive Web App (PWA) - Add to Home Screen

### Steps:

1. **Create a Web App Manifest** (`mobile/public/manifest.json`):
   ```json
   {
     "name": "Project Inside",
     "short_name": "Inside",
     "description": "Relationship coaching platform",
     "start_url": "/",
     "display": "standalone",
     "background_color": "#ffffff",
     "theme_color": "#1e293b",
     "icons": [
       {
         "src": "/icon-192.png",
         "sizes": "192x192",
         "type": "image/png"
       },
       {
         "src": "/icon-512.png",
         "sizes": "512x512",
         "type": "image/png"
       }
     ]
   }
   ```

2. **Update `index.html`** to include manifest and meta tags:
   ```html
   <head>
     <meta name="viewport" content="width=device-width, initial-scale=1.0">
     <meta name="apple-mobile-web-app-capable" content="yes">
     <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
     <meta name="apple-mobile-web-app-title" content="Inside">
     <link rel="manifest" href="/manifest.json">
     <link rel="apple-touch-icon" href="/icon-192.png">
   </head>
   ```

3. **Create app icons** (192x192 and 512x512 PNG files) in `mobile/public/`

4. **Build and serve:**
   ```bash
   npm run build
   npm run preview
   ```

5. **On iPhone:**
   - Open Safari
   - Navigate to your app URL
   - Tap Share button → "Add to Home Screen"
   - App will appear as an icon on home screen

### Pros:
- ✅ App-like experience
- ✅ No App Store needed
- ✅ Works offline (with service worker)

### Cons:
- ❌ Still requires network for API calls
- ❌ Limited native features

---

## Option 3: Native iOS App with Capacitor (Recommended for Production)

Capacitor wraps your web app in a native iOS container, allowing you to:
- Distribute via App Store
- Access native iOS features
- Better performance

### Steps:

1. **Install Capacitor:**
   ```bash
   cd mobile
   npm install @capacitor/core @capacitor/cli @capacitor/ios
   ```

2. **Initialize Capacitor:**
   ```bash
   npx cap init "Project Inside" "com.project.inside"
   ```

3. **Add iOS platform:**
   ```bash
   npx cap add ios
   ```

4. **Build your app:**
   ```bash
   npm run build
   ```

5. **Sync to iOS:**
   ```bash
   npx cap sync ios
   ```

6. **Open in Xcode:**
   ```bash
   npx cap open ios
   ```

7. **In Xcode:**
   - Select your development team
   - Connect iPhone via USB
   - Select your iPhone as the target device
   - Click Run (▶️) to build and install

**Microphone (voice print / live coaching):** The native app includes `NSMicrophoneUsageDescription` in `ios/App/App/Info.plist`. iOS only exposes the microphone API when this key is set. If you see "Microphone is not available", rebuild the app in Xcode after a fresh `npx cap sync ios`. If you open the app in Safari via `http://...` (Option 1), the mic requires a **secure context**—use HTTPS or the native app.

### Prerequisites:
- ✅ macOS computer
- ✅ Xcode installed (from App Store)
- ✅ Apple Developer account (free for development)
- ✅ iPhone connected via USB

### Pros:
- ✅ Native app experience
- ✅ Can distribute via App Store
- ✅ Access to native iOS APIs
- ✅ Better performance

### Cons:
- ❌ Requires macOS and Xcode
- ❌ More complex setup
- ❌ Need to rebuild for updates

---

## Option 3b: TestFlight (Dogfooding / Beta)

Use TestFlight to let testers install your app via a link **without** publishing to the public App Store. Good for dogfooding, internal testers, or a closed beta.

### Prerequisites

- **Apple Developer Program** membership ($99/year) – [developer.apple.com](https://developer.apple.com/programs/)
- macOS, Xcode, and a working native iOS build (Option 3 steps 1–6)

### 1. Create the app in App Store Connect

1. Go to [App Store Connect](https://appstoreconnect.apple.com) → **My Apps**.
2. Click **+** → **New App**.
3. Fill in:
   - **Platform:** iOS
   - **Name:** Project Inside (or your display name)
   - **Primary Language:** your choice
   - **Bundle ID:** select the one that matches your app (e.g. `com.project.inside` from `capacitor.config.ts`). If it’s not listed, create it under [Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/identifiers/list) → **Identifiers** → **+** → **App IDs**.
   - **SKU:** any unique string (e.g. `project-inside-001`)
4. Create the app (you can leave most optional fields blank for now).

### 2. Archive and upload from Xcode

1. **Build for release:**
   ```bash
   cd mobile
   npm run build
   npx cap sync ios
   npx cap open ios
   ```
2. In Xcode:
   - Select the **App** scheme and **Any iOS Device (arm64)** as the run destination (not a simulator).
   - Menu: **Product** → **Archive**.
3. When the archive finishes, the **Organizer** window opens. Select the new archive and click **Distribute App**.
4. Choose **App Store Connect** → **Upload** → **Next**.
5. Leave options as default (e.g. upload symbols, manage version and build number) → **Next**.
6. Select your **Distribution certificate** and **Provisioning profile** (Xcode usually manages these; choose **Automatically manage signing** if prompted).
7. Click **Upload** and wait for the upload to complete.

### 3. Submit the build for TestFlight

1. In [App Store Connect](https://appstoreconnect.apple.com) → **My Apps** → **Project Inside** (your app).
2. Open the **TestFlight** tab.
3. Under **iOS Builds**, your build will appear (status “Processing” at first; wait a few minutes up to ~30).
4. When the build is **Ready to Submit**, click it. Add **What to Test** (optional notes for testers), then click **Submit for Review**. TestFlight builds go through a short Apple review (often same day).

### 4. Add testers and get the link

**Internal testing (up to 100, same org):**

- **TestFlight** tab → **Internal Testing** → **+** to create a group → add testers by Apple ID (email). They get an email invite and install via the TestFlight app.

**External testing (up to 10,000, optional public link):**

- **TestFlight** tab → **External Testing** → **+** to create a group → add the build → add testers by email, or enable **Public Link** so anyone with the link can join (they still need to install the TestFlight app and accept the invite).
- Share the **Public Link** (or individual invites) with your dogfooders; they open it on their iPhone, install TestFlight if needed, then install your app.

### 5. Testers install the app

1. Install **TestFlight** from the App Store (if not already).
2. Open the invite link (or use the link from the TestFlight app).
3. Accept the invite and tap **Install** for Project Inside.

### Notes

- **Backend:** Ensure testers can reach your API. For production dogfooding, use your deployed backend (e.g. DigitalOcean) and set `VITE_API_BASE_URL` in the mobile build to that URL before archiving.
- **New builds:** For each update, create a new archive, upload, then add the new build to the same TestFlight group; testers get a notification to update.
- The app does **not** appear on the public App Store; only people with the TestFlight link or invite can install it.

---

## Option 4: Deploy to Web Hosting (Access Anywhere)

Deploy the built app to a hosting service so it's accessible from anywhere:

### Services:
- **Vercel** (recommended for Vite apps):
  ```bash
  npm install -g vercel
  vercel
  ```

- **Netlify:**
  ```bash
  npm install -g netlify-cli
  netlify deploy --prod
  ```

- **GitHub Pages:**
  - Build: `npm run build`
  - Deploy `dist/` folder to GitHub Pages

### Steps:
1. **Build the app:**
   ```bash
   npm run build
   ```

2. **Deploy to hosting service**

3. **Update API URL** to point to your production backend

4. **Access on iPhone** via the deployed URL

### Pros:
- ✅ Accessible from anywhere
- ✅ No local network required
- ✅ Easy updates

### Cons:
- ❌ Requires backend to be publicly accessible
- ❌ May have hosting costs

---

## Quick Start: Option 1 (Development Testing)

For quick testing on iPhone:

1. **Start backend:**
   ```bash
   cd backend
   make dev
   ```

2. **Start mobile app:**
   ```bash
   cd mobile
   npm run dev
   ```

3. **Find your IP:**
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   # Example output: inet 192.168.1.100
   ```

4. **Update `.env.local`:**
   ```bash
   VITE_API_BASE_URL=http://192.168.1.100:8000
   ```

5. **Restart dev server** and access `http://192.168.1.100:3000` on iPhone Safari

---

## Troubleshooting

### "Cannot connect to server"
- Ensure iPhone and computer are on same Wi-Fi network
- Check firewall allows connections on port 3000
- Verify IP address is correct

### CORS errors
- Make sure backend CORS_ORIGINS includes your IP
- Restart backend after changing CORS settings

### App not loading
- Check browser console for errors
- Verify API_BASE_URL is correct
- Ensure backend is running

---

## Recommended Approach

- **Development/Testing:** Use Option 1 (Mobile Browser)
- **Beta Testing:** Use Option 2 (PWA - Add to Home Screen)
- **Production:** Use Option 3 (Capacitor + App Store) or Option 4 (Web Hosting)
