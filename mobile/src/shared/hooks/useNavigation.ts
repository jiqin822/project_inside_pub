import { useCallback } from 'react';
import { AppMode } from '../types/domain';

// Simple navigation hook - will be replaced with React Router later
// For now, this provides a consistent interface
interface NavigationContext {
  navigate: (mode: AppMode) => void;
  goBack: () => void;
  replace: (mode: AppMode) => void;
}

// This will be provided by a navigation context in Phase 8
// For now, return a no-op implementation
export const useNavigation = (): NavigationContext => {
  const navigate = useCallback((mode: AppMode) => {
    // TODO: Implement with React Router in Phase 8
    console.log('Navigate to:', mode);
  }, []);

  const goBack = useCallback(() => {
    // TODO: Implement with React Router in Phase 8
    console.log('Go back');
  }, []);

  const replace = useCallback((mode: AppMode) => {
    // TODO: Implement with React Router in Phase 8
    console.log('Replace with:', mode);
  }, []);

  return { navigate, goBack, replace };
};
