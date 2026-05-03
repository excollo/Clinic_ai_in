import { create } from "zustand";

export type VisitTabKey = "previsit" | "vitals" | "transcription" | "clinical_note" | "recap";

export interface VisitState {
  visitId: string;
  patientId: string;
  patientName: string;
  patientAge: number;
  patientSex: string;
  tokenNumber: string;
  visitType: "walk_in" | "scheduled";
  status: "in_consult" | "done";
  activeTab: VisitTabKey;
  completedTabs: Set<string>;
  chiefComplaint: string;
  setVisit: (payload: Omit<VisitState, "setVisit" | "setActiveTab" | "markTabComplete" | "setStatus" | "hydrateServerProgress">) => void;
  setActiveTab: (tab: VisitTabKey) => void;
  markTabComplete: (tab: VisitTabKey) => void;
  setStatus: (status: "in_consult" | "done") => void;
  /** Merge server-derived completed steps (e.g. revisiting a visit with saved data). */
  hydrateServerProgress: (completedTabs: VisitTabKey[]) => void;
}

export const useVisitStore = create<VisitState>((set) => ({
  visitId: "",
  patientId: "",
  patientName: "",
  patientAge: 0,
  patientSex: "",
  tokenNumber: "",
  visitType: "walk_in",
  status: "in_consult",
  activeTab: "previsit",
  completedTabs: new Set<string>(),
  chiefComplaint: "",
  setVisit: (payload) => set({ ...payload }),
  setActiveTab: (activeTab) => set({ activeTab }),
  markTabComplete: (tab) =>
    set((state) => {
      const next = new Set(state.completedTabs);
      next.add(tab);
      return { completedTabs: next };
    }),
  setStatus: (status) => set({ status }),
  hydrateServerProgress: (completedTabs) =>
    set((state) => {
      const order: VisitTabKey[] = ["previsit", "vitals", "transcription", "clinical_note", "recap"];
      const next = new Set(state.completedTabs);
      completedTabs.forEach((t) => next.add(t));
      const firstOpen = order.find((t) => !next.has(t));
      return {
        completedTabs: next,
        activeTab: firstOpen ?? "recap",
      };
    }),
}));
