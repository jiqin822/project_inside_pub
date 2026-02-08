# Fixing "Command PhaseScriptExecution failed" Error

This error typically occurs when Capacitor tries to copy files that don't exist or when build scripts fail.

## Solution 1: Build the App First (Most Common)

The `dist` folder must exist before building in Xcode:

```bash
cd mobile
npm run build
npx cap sync ios
```

Then try building in Xcode again.

## Solution 2: Check Build Scripts

1. **In Xcode**, go to your target's **Build Phases**
2. Look for any **Run Script** phases
3. Check if they're trying to access files that don't exist
4. Common scripts that might fail:
   - Copying from `dist/` folder
   - Running `node` commands
   - Copying `node_modules`

## Solution 3: Clean Build Folder

In Xcode:
1. **Product** → **Clean Build Folder** (or `Shift + Cmd + K`)
2. Close Xcode
3. Delete derived data:
   ```bash
   rm -rf ~/Library/Developer/Xcode/DerivedData
   ```
4. Reopen Xcode and try again

## Solution 4: Check Node Path

If build scripts use Node, ensure Xcode can find it:

```bash
# Find Node path
which node

# Add to Xcode build script if needed:
export PATH="/usr/local/bin:$PATH"
```

## Solution 5: Verify Capacitor Sync

Make sure Capacitor is properly synced:

```bash
cd mobile

# Ensure dependencies are installed
npm install

# Build the app
npm run build

# Sync to iOS (this copies dist/ to iOS project)
npx cap sync ios

# Open in Xcode
npx cap open ios
```

## Solution 6: Check File References

In Xcode:
1. Check if `dist` folder or `public` folder is referenced
2. If they're red (missing), remove the reference
3. Run `npx cap sync ios` again to re-add them

## Solution 7: Check Console for Specific Error

In Xcode:
1. Open the **Report Navigator** (⌘9)
2. Click on the failed build
3. Expand the error to see the specific script that failed
4. Look for error messages like:
   - "No such file or directory"
   - "Command not found"
   - "Permission denied"

## Solution 8: Disable Build Scripts Temporarily

If a specific script is failing:
1. In Xcode → **Build Phases**
2. Find the failing script
3. Uncheck "For install builds only" or disable it temporarily
4. Try building again

## Quick Fix Checklist

Run these commands in order:

```bash
cd mobile

# 1. Install/update dependencies
npm install

# 2. Build the app (creates dist/)
npm run build

# 3. Sync to iOS
npx cap sync ios

# 4. Open in Xcode
npx cap open ios
```

Then in Xcode:
- **Product** → **Clean Build Folder**
- **Product** → **Build** (or ⌘B)

## Common Causes

1. ❌ **dist folder doesn't exist** → Run `npm run build`
2. ❌ **node_modules missing** → Run `npm install`
3. ❌ **Capacitor out of sync** → Run `npx cap sync ios`
4. ❌ **Xcode cache issues** → Clean build folder
5. ❌ **Path issues** → Check script paths in Build Phases

## Still Not Working?

Check the detailed error in Xcode:
1. Click the error in the Issue Navigator
2. Look at the full error message
3. Check which specific script/command failed
4. Share the error message for more specific help
