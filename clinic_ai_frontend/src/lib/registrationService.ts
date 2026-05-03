import apiClient from "@/lib/apiClient";

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
  /** When set to `in_clinic`, scheduled visits skip WhatsApp intake. Default for scheduled is WhatsApp on the server if omitted. */
  intake_mode?: "whatsapp" | "in_clinic";
};

export async function registerPatient(input: RegisterPatientInput) {
  const response = await apiClient.post("/patients/register", input);
  return response.data as {
    patient_id: string;
    visit_id: string;
    token_number: string | null;
    consent_required: boolean;
    whatsapp_triggered?: boolean;
  };
}
