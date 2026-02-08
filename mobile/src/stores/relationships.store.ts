import { create } from "zustand";
import type { LovedOne } from "../shared/types/domain";

type RelationshipsState = {
  relationships: LovedOne[];
  activeRelationshipId: string | null;

  setRelationships: (rels: LovedOne[]) => void;
  setActiveRelationship: (id: string | null) => void;
  getActiveRelationship: () => LovedOne | undefined;
};

export const useRelationshipsStore = create<RelationshipsState>((set, get) => ({
  relationships: [],
  activeRelationshipId: null,

  setRelationships: (rels) => set({ relationships: rels }),
  
  setActiveRelationship: (id) => set({ activeRelationshipId: id }),
  
  getActiveRelationship: () => {
    const state = get();
    if (!state.activeRelationshipId) return undefined;
    return state.relationships.find((r) => r.id === state.activeRelationshipId);
  },
}));
