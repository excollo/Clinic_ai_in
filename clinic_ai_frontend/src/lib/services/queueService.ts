import apiClient from "@/lib/apiClient";

type QueueApiRow = {
  patient_id?: string;
  visit_id?: string;
  token_number?: string;
  name?: string;
  age?: number | null;
  sex?: string | null;
  status?: string;
  visit_type?: string;
  chief_complaint?: string;
  careprep_ready?: boolean;
  red_flags?: string[] | null;
};

export type QueueRow = {
  patientId: string;
  visitId: string;
  token: string;
  patientName: string;
  age: number;
  sex: "male" | "female" | "other";
  reviewed: boolean;
  visitType: "walk_in" | "scheduled";
  hasRedFlag: boolean;
  redFlags: string[];
  chiefComplaint: string;
  status: "waiting" | "in_consult" | "done";
  language: string;
  questionCount: number;
  imageCount: number;
};

function normalizeSex(value: string | null | undefined): "male" | "female" | "other" {
  const sex = String(value || "").toLowerCase();
  if (sex === "m" || sex === "male") return "male";
  if (sex === "f" || sex === "female") return "female";
  return "other";
}

function normalizeVisitType(value: string | null | undefined): "walk_in" | "scheduled" {
  return String(value || "").toLowerCase() === "scheduled" ? "scheduled" : "walk_in";
}

function normalizeStatus(value: string | null | undefined): "waiting" | "in_consult" | "done" {
  const status = String(value || "").toLowerCase();
  if (status === "done" || status === "completed") return "done";
  if (status === "in_consult") return "in_consult";
  return "waiting";
}

export async function fetchDoctorQueue(doctorId: string): Promise<QueueRow[]> {
  if (!doctorId) return [];
  const response = await apiClient.get(`/doctor/${doctorId}/queue`);
  const rows = Array.isArray(response.data?.patients) ? (response.data.patients as QueueApiRow[]) : [];
  return rows.map((row) => {
    const redFlags = Array.isArray(row.red_flags) ? row.red_flags.filter(Boolean) : [];
    const status = normalizeStatus(row.status);
    return {
      patientId: String(row.patient_id || ""),
      visitId: String(row.visit_id || ""),
      token: String(row.token_number || ""),
      patientName: String(row.name || "Patient"),
      age: Number(row.age || 0),
      sex: normalizeSex(row.sex),
      reviewed: status === "done",
      visitType: normalizeVisitType(row.visit_type),
      hasRedFlag: redFlags.length > 0,
      redFlags,
      chiefComplaint: String(row.chief_complaint || ""),
      status,
      language: "hindi",
      questionCount: 0,
      imageCount: 0,
    };
  });
}
