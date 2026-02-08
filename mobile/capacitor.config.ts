import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.project.inside',
  appName: 'Project Inside',
  webDir: 'dist',
  plugins: {
    StatusBar: {
      overlaysWebView: false,      // Disable status bar overlay so webview starts below status bar
      style: 'DARK',
      backgroundColor: '#ffffff'
    }
  }
};

export default config;
