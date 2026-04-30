import { create } from "zustand";

type SignupDraft = {
  fullName: string;
  mobile: string;
  email: string;
  regNo: string;
  specialty: string;
  password: string;
  clinicName: string;
  city: string;
  pincode: string;
  opdStart: string;
  opdEnd: string;
  languages: string[];
  tokenPrefix: string;
  hfrId: string;
  whatsappChoice: "platform_default" | "own_number";
  otpRequestId: string;
};

type Store = {
  signup: SignupDraft;
  updateSignup: (payload: Partial<SignupDraft>) => void;
  resetSignup: () => void;
};

const initialDraft: SignupDraft = {
  fullName: "",
  mobile: "",
  email: "",
  regNo: "",
  specialty: "",
  password: "",
  clinicName: "",
  city: "",
  pincode: "",
  opdStart: "",
  opdEnd: "",
  languages: ["hindi", "english"],
  tokenPrefix: "OPD-",
  hfrId: "",
  whatsappChoice: "platform_default",
  otpRequestId: "",
};

const localStorageKey = "clinic_signup_draft";

function readInitial(): SignupDraft {
  try {
    const parsed = localStorage.getItem(localStorageKey);
    if (!parsed) return initialDraft;
    return { ...initialDraft, ...(JSON.parse(parsed) as Partial<SignupDraft>) };
  } catch {
    return initialDraft;
  }
}

export const useAuthFlowStore = create<Store>((set) => ({
  signup: readInitial(),
  updateSignup: (payload) =>
    set((state) => {
      const next = { ...state.signup, ...payload };
      localStorage.setItem(localStorageKey, JSON.stringify(next));
      return { signup: next };
    }),
  resetSignup: () => {
    localStorage.removeItem(localStorageKey);
    set({ signup: initialDraft });
  },
}));
