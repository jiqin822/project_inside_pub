import { create } from 'zustand';
import { LovedOne } from '../../../types';

interface RelationshipState {
  relationships: LovedOne[];
  activeRelationshipId: string | null;
  loading: boolean;
  error: string | null;

  // Actions
  setRelationships: (relationships: LovedOne[]) => void;
  setActiveRelationship: (id: string | null) => void;
  addRelationship: (relationship: LovedOne) => void;
  updateRelationship: (id: string, updates: Partial<LovedOne>) => void;
  removeRelationship: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Computed selectors
  activeRelationship: () => LovedOne | undefined;
  getRelationshipById: (id: string) => LovedOne | undefined;
}

export const useRelationshipStore = create<RelationshipState>((set, get) => ({
  relationships: [],
  activeRelationshipId: null,
  loading: false,
  error: null,

  setRelationships: (relationships) => set({ relationships }),

  setActiveRelationship: (id) => set({ activeRelationshipId: id }),

  addRelationship: (relationship) => set((state) => ({
    relationships: [...state.relationships, relationship],
  })),

  updateRelationship: (id, updates) => set((state) => ({
    relationships: state.relationships.map((rel) =>
      rel.id === id ? { ...rel, ...updates } : rel
    ),
  })),

  removeRelationship: (id) => set((state) => ({
    relationships: state.relationships.filter((rel) => rel.id !== id),
    activeRelationshipId: state.activeRelationshipId === id ? null : state.activeRelationshipId,
  })),

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error }),

  activeRelationship: () => {
    const state = get();
    if (!state.activeRelationshipId) return undefined;
    return state.relationships.find((rel) => rel.id === state.activeRelationshipId);
  },

  getRelationshipById: (id) => {
    return get().relationships.find((rel) => rel.id === id);
  },
}));
