import apiClient from "@/lib/apiClient";

type IntakeSessionApi = {
  visit_id?: string;
  patient_id?: string;
  status?: string;
  illness?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  question_answers?: Array<{
    question?: string;
    answer?: string;
    topic?: string | null;
  }>;
};

export type CareprepSessionRow = {
  visitId: string;
  patientId: string;
  patientName: string;
  mobile: string;
  token: string;
  status: string;
  intakeStatus: string;
  illness: string;
  questionCount: number;
  updatedAt: string | null;
};

export type IntakeQuestionAnswer = {
  question: string;
  answer: string;
  topic?: string | null;
};

export type CareprepSessionDetail = {
  visitId: string;
  patientId: string;
  intakeStatus: string;
  illness: string;
  updatedAt: string | null;
  createdAt: string | null;
  questionAnswers: IntakeQuestionAnswer[];
};

type IntakeSessionsApiRow = {
  visit_id?: string;
  patient_id?: string;
  patient_name?: string;
  mobile?: string;
  token_number?: string;
  visit_status?: string;
  workflow_type?: string;
  intake_status?: string;
  question_count?: number;
  illness?: string;
  updated_at?: string | null;
  created_at?: string | null;
};

type IntakeSessionsListResponse = {
  sessions?: IntakeSessionsApiRow[];
  total?: number;
};

/** True when the API returned a real intake session (not the empty placeholder). */
export function intakeSessionApiHasForm(intake: IntakeSessionApi | null | undefined): boolean {
  if (!intake) return false;
  const qa = Array.isArray(intake.question_answers) ? intake.question_answers : [];
  if (qa.length > 0) return true;
  if (String(intake.illness || "").trim().length > 0) return true;
  const st = String(intake.status || "").toLowerCase();
  if (st && st !== "not_started") return true;
  if (intake.updated_at || intake.created_at) return true;
  return false;
}

export function careprepDetailHasIntake(d: CareprepSessionDetail): boolean {
  if (d.questionAnswers.length > 0) return true;
  if (d.illness.trim().length > 0) return true;
  if (d.intakeStatus && d.intakeStatus !== "not_started") return true;
  if (d.updatedAt || d.createdAt) return true;
  return false;
}

/** All intake-backed visits for this doctor (any date), newest activity first. */
export async function fetchCareprepSessions(doctorId: string): Promise<CareprepSessionRow[]> {
  if (!doctorId) return [];
  const res = await apiClient.get(`/doctor/${doctorId}/intake-sessions`, {
    params: { limit: 500, offset: 0 },
  });
  const body = res.data as IntakeSessionsListResponse;
  const sessions = Array.isArray(body.sessions) ? body.sessions : [];
  return sessions.map((s) => ({
    visitId: String(s.visit_id || ""),
    patientId: String(s.patient_id || ""),
    patientName: String(s.patient_name || "Patient"),
    mobile: String(s.mobile || ""),
    token: String(s.token_number || ""),
    status: String(s.visit_status || ""),
    intakeStatus: String(s.intake_status || "not_started"),
    illness: String(s.illness || ""),
    questionCount: Number(s.question_count ?? 0),
    updatedAt: s.updated_at != null ? String(s.updated_at) : null,
  }));
}

export async function fetchCareprepSessionByVisitId(visitId: string): Promise<CareprepSessionDetail> {
  const response = await apiClient.get(`/api/visits/${visitId}/intake-session`);
  const data = response.data as IntakeSessionApi;
  return {
    visitId: String(data.visit_id || visitId),
    patientId: String(data.patient_id || ""),
    intakeStatus: String(data.status || "not_started"),
    illness: String(data.illness || ""),
    updatedAt: data.updated_at || null,
    createdAt: data.created_at || null,
    questionAnswers: (data.question_answers || []).map((qa) => ({
      question: String(qa.question || ""),
      answer: String(qa.answer || ""),
      topic: qa.topic || null,
    })),
  };
}
