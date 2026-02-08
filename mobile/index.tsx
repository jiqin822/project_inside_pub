import React from 'react';
import ReactDOM from 'react-dom/client';
import { Capacitor } from '@capacitor/core';
import { AppShell } from './src/app/AppShell';
import App from './App';

// Setup status bar for iOS
async function setupStatusBar() {
  // Only run in native iOS environment
  if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios') {
    try {
      // Dynamic import - only loads in Capacitor environment
      const statusBarModule = await import('@capacitor/status-bar');
      const { StatusBar, Style } = statusBarModule;
      
      await StatusBar.setOverlaysWebView({ overlay: false });
      await StatusBar.setStyle({ style: Style.Dark });
      await StatusBar.setBackgroundColor({ color: '#ffffff' });
    } catch (error) {
      // StatusBar plugin might not be available
      console.log('StatusBar setup skipped:', error);
    }
  }
}

// Only setup status bar if we're in a native environment
if (typeof window !== 'undefined') {
  setupStatusBar();
}

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <AppShell>
      <App />
    </AppShell>
  </React.StrictMode>
);
