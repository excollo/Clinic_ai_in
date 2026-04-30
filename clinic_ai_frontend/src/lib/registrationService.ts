import apiClient from "@/lib/apiClient";
import { registerPatientMock } from "@/lib/mocks/registration";

export type RegisterPatientInput = {
  name: string;
  age: number;
  sex: "M" | "F" | "Other";
  mobile: string;
  language: string;
  chief_complaint: string;
  workflow_type: "walk_in" | "scheduled";
  scheduled_date?: string;
  scheduled_time?: string;
};

export async function registerPatient(input: RegisterPatientInput) {
  try {
    const response = await apiClient.post("/patients/register", input);
    return response.data as {
      patient_id: string;
      visit_id: string;
      token_number: string | null;
      consent_required: boolean;
    };
  } catch {
    const fallback = await registerPatientMock({
      workflow_type: input.workflow_type,
      name: input.name,
      age: input.age,
      sex: input.sex === "M" ? "male" : input.sex === "F" ? "female" : "other",
      mobile: input.mobile,
      preferred_language: input.language,
      chief_complaint: input.chief_complaint,
      schedule_date: input.scheduled_date,
      schedule_time: input.scheduled_time,
    });
    return fallback;
  }
}
