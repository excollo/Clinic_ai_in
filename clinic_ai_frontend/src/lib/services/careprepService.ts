import apiClient from "@/lib/apiClient";

type QueueApiRow = {
  patient_id?: string;
  visit_id?: string;
  token_number?: string;
  name?: string;
  status?: string;
};

type IntakeSessionApi = {
  visit_id?: string;
  patient_id?: string;
  status?: string;
  illness?: string | null;
  updated_at?: string | null;
  question_answers?: Array<{
    question?: string;
    answer?: string;
    topic?: string | null;
  }>;
};

type PatientApi = {
  patient_id?: string;
  name?: string;
  mobile?: string;
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
  questionAnswers: IntakeQuestionAnswer[];
};

export async function fetchCareprepSessions(doctorId: string): Promise<CareprepSessionRow[]> {
  if (!doctorId) return [];
  const [queueResponse, patientsResponse] = await Promise.all([
    apiClient.get(`/doctor/${doctorId}/queue`),
    apiClient.get("/patients", { params: { limit: 500, offset: 0, search: "", filter: "all" } }),
  ]);
  const queueRows = Array.isArray(queueResponse.data?.patients) ? (queueResponse.data.patients as QueueApiRow[]) : [];
  const patientRows = Array.isArray(patientsResponse.data?.patients) ? (patientsResponse.data.patients as PatientApi[]) : [];
  const patientById = new Map<string, PatientApi>();
  patientRows.forEach((row) => {
    const pid = String(row.patient_id || "");
    if (pid) patientById.set(pid, row);
  });

  const details = await Promise.all(
    queueRows.map(async (row) => {
      const visitId = String(row.visit_id || "");
      if (!visitId) return null;
      try {
        const intake = await apiClient.get(`/api/visits/${visitId}/intake-session`);
        return { visitId, intake: intake.data as IntakeSessionApi, queue: row };
      } catch {
        return { visitId, intake: null, queue: row };
      }
    }),
  );

  return details
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .map((item) => {
      const patientId = String(item.queue.patient_id || item.intake?.patient_id || "");
      const patient = patientById.get(patientId);
      const questionAnswers = Array.isArray(item.intake?.question_answers) ? item.intake?.question_answers : [];
      return {
        visitId: item.visitId,
        patientId,
        patientName: String(item.queue.name || patient?.name || "Patient"),
        mobile: String(patient?.mobile || ""),
        token: String(item.queue.token_number || ""),
        status: String(item.queue.status || "waiting"),
        intakeStatus: String(item.intake?.status || "not_started"),
        illness: String(item.intake?.illness || ""),
        questionCount: questionAnswers.length,
        updatedAt: item.intake?.updated_at || null,
      };
    });
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
    questionAnswers: (data.question_answers || []).map((qa) => ({
      question: String(qa.question || ""),
      answer: String(qa.answer || ""),
      topic: qa.topic || null,
    })),
  };
}
