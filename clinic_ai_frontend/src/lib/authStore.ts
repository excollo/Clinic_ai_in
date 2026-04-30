import { create } from "zustand";

type Session = {
  apiKey: string;
  doctorId: string;
  doctorName: string;
  mobile: string;
};

type AuthState = {
  apiKey: string | null;
  doctorId: string | null;
  doctorName: string | null;
  mobile: string | null;
  setSession: (session: Session) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  apiKey: localStorage.getItem("clinic_api_key"),
  doctorId: localStorage.getItem("clinic_doctor_id"),
  doctorName: localStorage.getItem("clinic_doctor_name"),
  mobile: localStorage.getItem("clinic_mobile"),
  setSession: (session) => {
    localStorage.setItem("clinic_api_key", session.apiKey);
    localStorage.setItem("clinic_doctor_id", session.doctorId);
    localStorage.setItem("clinic_doctor_name", session.doctorName);
    localStorage.setItem("clinic_mobile", session.mobile);
    set(session);
  },
  clearSession: () => {
    localStorage.removeItem("clinic_api_key");
    localStorage.removeItem("clinic_doctor_id");
    localStorage.removeItem("clinic_doctor_name");
    localStorage.removeItem("clinic_mobile");
    set({ apiKey: null, doctorId: null, doctorName: null, mobile: null });
  },
}));
