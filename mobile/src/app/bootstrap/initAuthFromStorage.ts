import { useSessionStore } from "../../stores/session.store";

/**
 * Bootstrap function to initialize auth state from localStorage
 * Call this early in AppShell or App initialization
 */
export const initAuthFromStorage = async () => {
  const store = useSessionStore.getState();
  
  // Hydrate tokens from storage
  store.hydrateFromStorage();
  
  // If we have a token, try to fetch the current user
  if (store.accessToken) {
    try {
      await store.fetchMe();
    } catch (error) {
      // Token might be invalid, clear session
      console.warn("Failed to fetch user with stored token, clearing session");
      store.clearSession();
    }
  }
};
