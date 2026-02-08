import React from 'react';
import { QueryProvider } from './providers/QueryProvider';
import { BrowserRouter } from 'react-router-dom';
import { Routes } from './routes';
import { ErrorBoundary } from './ErrorBoundary';

interface AppShellProps {
  children?: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  // For backward compatibility, render children if provided
  // This allows App.tsx to continue working with its existing mode-based routing
  if (children) {
    return (
      <ErrorBoundary>
        <QueryProvider>
          {children}
        </QueryProvider>
      </ErrorBoundary>
    );
  }

  // Use React Router for routing (when children not provided)
  return (
    <ErrorBoundary>
      <QueryProvider>
        <BrowserRouter>
          <Routes />
        </BrowserRouter>
      </QueryProvider>
    </ErrorBoundary>
  );
};
