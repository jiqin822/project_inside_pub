import React, { useEffect } from 'react';
import { Routes as RouterRoutes, Route, Navigate } from 'react-router-dom';
import { useSessionStore } from '../stores/session.store';
import { useUiStore } from '../stores/ui.store';
import App from '../../App'; // Temporary - will be replaced with individual screens

/**
 * Routes component that decides which screen to show based on:
 * - Session status (logged in)
 * - Onboarding status
 * - Invite route
 * - Current "room" route
 */
export const Routes: React.FC = () => {
  const { status, me } = useSessionStore();
  const { room, setRoom } = useUiStore();

  // Sync UI store room with URL (for now, keep App.tsx mode system)
  // This will be replaced when we fully migrate to React Router

  const isAuthenticated = status === "authenticated" && !!me;
  const isLoading = status === "loading";

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto mb-4"></div>
          <p className="text-sm text-slate-500">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <RouterRoutes>
      {/* Public routes: /signup is used by invite links (e.g. base/signup?token=xxx) */}
      <Route path="/auth" element={<App />} />
      <Route path="/signup" element={<App />} />
      <Route path="/invite/:token" element={<App />} />
      
      {/* Protected routes */}
      {isAuthenticated ? (
        <>
          <Route path="/" element={<App />} />
          <Route path="/onboarding" element={<App />} />
          <Route path="/dashboard" element={<App />} />
          <Route path="/rooms/live-coach" element={<App />} />
          <Route path="/rooms/rewards" element={<App />} />
          <Route path="/rooms/love-maps" element={<App />} />
          <Route path="/rooms/therapist" element={<App />} />
          <Route path="/rooms/activities" element={<App />} />
          <Route path="/profile" element={<App />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </>
      ) : (
        <Route path="*" element={<Navigate to="/auth" replace />} />
      )}
    </RouterRoutes>
  );
};
