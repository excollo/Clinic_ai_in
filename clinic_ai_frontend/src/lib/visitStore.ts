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
  setVisit: (payload: Omit<VisitState, "setVisit" | "setActiveTab" | "markTabComplete" | "setStatus">) => void;
  setActiveTab: (tab: VisitTabKey) => void;
  markTabComplete: (tab: VisitTabKey) => void;
  setStatus: (status: "in_consult" | "done") => void;
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
}));
