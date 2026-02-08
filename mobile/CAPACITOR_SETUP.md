# Capacitor Setup - Already Configured! ✅

Capacitor is already set up for your mobile app. You don't need to run `npx cap init` again.

## Current Setup

- ✅ Capacitor config: `capacitor.config.ts`
- ✅ iOS platform: `ios/` directory exists
- ✅ Dependencies: Already installed

## Deploy to iPhone

### Step 1: Build the App

```bash
cd mobile
npm run build
```

This creates a `dist/` folder with your production build.

### Step 2: Sync to iOS

```bash
npx cap sync ios
```

This copies your built app to the iOS project.

### Step 3: Open in Xcode

```bash
npx cap open ios
```

This opens the project in Xcode.

### Step 4: Deploy to iPhone

In Xcode:

1. **Select your development team:**
   - Click on the project in the left sidebar
   - Select "Signing & Capabilities" tab
   - Choose your Apple ID/Team

2. **Connect your iPhone:**
   - Connect iPhone via USB
   - Unlock iPhone and trust the computer if prompted

3. **Select iPhone as target:**
   - At the top, next to the play button, select your iPhone from the device list

4. **Build and Run:**
   - Click the Play button (▶️) or press `Cmd + R`
   - Xcode will build and install the app on your iPhone

### Troubleshooting

#### "No signing certificate found"
- Go to Xcode → Preferences → Accounts
- Add your Apple ID
- Select your team in Signing & Capabilities

#### "Unable to install app"
- On iPhone: Settings → General → VPN & Device Management
- Trust your developer certificate

#### "Build failed"
- Make sure you ran `npm run build` first
- Run `npx cap sync ios` to update iOS project
- Clean build folder in Xcode: Product → Clean Build Folder

## Update App After Changes

When you make changes to your app:

```bash
# 1. Build the app
npm run build

# 2. Sync to iOS
npx cap sync ios

# 3. Open in Xcode and run again
npx cap open ios
```

## Configuration

Your current config (`capacitor.config.ts`):
- **App ID:** `com.project.inside`
- **App Name:** `Project Inside`
- **Web Directory:** `dist` (Vite build output)

To change these, edit `capacitor.config.ts` and run `npx cap sync ios` again.
