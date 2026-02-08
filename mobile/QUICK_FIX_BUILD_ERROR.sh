#!/bin/bash
# Quick fix for Xcode build errors

echo "🔧 Fixing Xcode build error..."

cd "$(dirname "$0")"

echo "1. Building the app..."
npm run build

echo "2. Syncing Capacitor..."
npx cap sync ios

echo "3. Cleaning Xcode derived data..."
rm -rf ~/Library/Developer/Xcode/DerivedData/*

echo "✅ Done! Now:"
echo "   1. Open Xcode"
echo "   2. Product → Clean Build Folder (Shift+Cmd+K)"
echo "   3. Product → Build (Cmd+B)"
