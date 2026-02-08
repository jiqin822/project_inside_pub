import React from 'react';

interface StoreProviderProps {
  children: React.ReactNode;
}

export const StoreProvider: React.FC<StoreProviderProps> = ({ children }) => {
  // Stores are created with Zustand and don't need a provider wrapper
  // This component exists for consistency and future extensibility
  return <>{children}</>;
};
