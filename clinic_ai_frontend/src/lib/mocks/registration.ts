import { normalizeIndianMobile } from "@/lib/format";

export type RegisterPayload = {
  workflow_type: "walk_in" | "scheduled";
  name: string;
  age: number;
  sex: "male" | "female" | "other";
  mobile: string;
  preferred_language: string;
  chief_complaint: string;
  schedule_date?: string;
  schedule_time?: string;
};

export async function registerPatientMock(payload: RegisterPayload) {
  await new Promise((resolve) => setTimeout(resolve, 350));
  return {
    patient_id: `pat_${btoa(`${payload.name}_${normalizeIndianMobile(payload.mobile)}`).replace(/=/g, "").slice(0, 12)}`,
    visit_id: `vis_${Math.random().toString(36).slice(2, 10)}`,
    token_number: "OPD-13",
    consent_required: true,
    workflow_type: payload.workflow_type,
  };
}

export function getMockSlots() {
  const slots: Array<{ label: string; value: string; available: boolean }> = [];
  for (let hour = 9; hour < 19; hour += 1) {
    for (let minute = 0; minute < 60; minute += 15) {
      const h12 = hour > 12 ? hour - 12 : hour;
      const ampm = hour >= 12 ? "PM" : "AM";
      const m = minute.toString().padStart(2, "0");
      const label = `${h12}:${m} ${ampm}`;
      slots.push({ label, value: `${hour.toString().padStart(2, "0")}:${m}`, available: Math.random() > 0.3 });
    }
  }
  return slots;
}
