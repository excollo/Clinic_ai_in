import apiClient from "@/lib/apiClient";
import type { TranscriptionResult, TranscriptionSegment } from "@/api/types";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const DEFAULT_MAX_WAIT_MS = 8 * 60 * 1000;
const MAX_POLL_INTERVAL_MS = 10_000;
const INITIAL_POLL_INTERVAL_MS = 2_000;

export class TranscriptionJobError extends Error {
  statusPayload: unknown;

  constructor(message: string, statusPayload: unknown) {
    super(message);
    this.name = "TranscriptionJobError";
    this.statusPayload = statusPayload;
  }
}

export type TranscriptionStatus = "queued" | "processing" | "completed" | "failed" | "timeout" | "pending";

export type TranscriptionJobStatusPayload = {
  jobId?: string;
  status?: TranscriptionStatus;
  message?: string;
  errorMessage?: string;
  errorCode?: string;
  transcript?: string | null;
};

export type StartTranscriptionResponse = {
  jobId: string;
  status: "queued" | "processing" | "completed" | "failed" | "timeout";
  message?: string;
};

export type PollResult =
  | { kind: "completed"; result: TranscriptionResult; jobId: string; lastPayload: unknown }
  | { kind: "still_processing"; jobId: string; lastPayload: unknown; message: string };

function speakerFromTurn(turn: Record<string, string>): "Doctor" | "Patient" | "Attendant" {
  const key = Object.keys(turn)[0] ?? "Patient";
  if (key.toLowerCase().includes("doctor")) return "Doctor";
  if (key.toLowerCase().includes("family")) return "Attendant";
  return "Patient";
}

function toTimestamp(index: number): string {
  const total = index * 5;
  const mm = Math.floor(total / 60);
  const ss = total % 60;
  return `${mm}:${String(ss).padStart(2, "0")}`;
}

function adaptDialogueResponse(
  dialogue: Array<Record<string, string>>,
  language: string,
  transcriptId: string,
): TranscriptionResult {
  const segments: TranscriptionSegment[] = dialogue.map((turn, index) => {
    const speaker = speakerFromTurn(turn);
    const text = String(Object.values(turn)[0] ?? "");
    return {
      speaker,
      timestamp: toTimestamp(index + 1),
      text,
      confidence: 0.94,
    };
  });
  return {
    transcript_id: transcriptId,
    segments,
    average_confidence: segments.length ? segments.reduce((a, b) => a + b.confidence, 0) / segments.length : 0,
    language_detected: language,
  };
}

/** True when structured turns contain non-empty dialogue text (API may omit or null this while transcript exists). */
function structuredDialogueHasContent(dialogue: unknown): dialogue is Array<Record<string, string>> {
  if (!Array.isArray(dialogue) || dialogue.length === 0) {
    return false;
  }
  return dialogue.some((turn) => {
    if (!turn || typeof turn !== "object") return false;
    const text = String(Object.values(turn as Record<string, unknown>)[0] ?? "").trim();
    return text.length > 0;
  });
}

/**
 * Builds UI segments from GET /dialogue payload. Uses structured_dialogue when present;
 * otherwise falls back to plain `transcript` (stored in DB) so reopened visits always show content.
 */
export function transcriptionResultFromDialoguePayload(
  data: {
    structured_dialogue?: unknown;
    transcript?: string | null;
    audio_file_path?: string | null;
  },
  languageMix: string,
  transcriptIdFallback: string,
): TranscriptionResult {
  const transcriptId = String(data?.audio_file_path ?? transcriptIdFallback);
  const structuredRaw = data?.structured_dialogue;
  if (structuredDialogueHasContent(structuredRaw)) {
    return adaptDialogueResponse(structuredRaw as Array<Record<string, string>>, String(languageMix || "en"), transcriptId);
  }
  const raw = String(data?.transcript ?? "").trim();
  if (raw.length > 0) {
    const chunks = raw
      .split(/\n\n+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    const parts = chunks.length > 0 ? chunks : [raw];
    const segments: TranscriptionSegment[] = parts.map((text, index) => ({
      speaker: "Patient",
      timestamp: toTimestamp(index + 1),
      text,
      confidence: 0.85,
    }));
    return {
      transcript_id: transcriptId,
      segments,
      average_confidence: 0.85,
      language_detected: String(languageMix || "en"),
    };
  }
  return {
    transcript_id: transcriptId,
    segments: [],
    average_confidence: 0,
    language_detected: String(languageMix || "en"),
  };
}

export function extractApiErrorMessage(error: unknown): string {
  const maybe = error as {
    response?: { data?: { detail?: string; message?: string } };
    message?: string;
  };
  return String(
    maybe?.response?.data?.detail ||
      maybe?.response?.data?.message ||
      maybe?.message ||
      "transcription failed",
  );
}

export async function transcribeVisitAudio(params: {
  patientId: string;
  visitId: string;
  audioBlob: Blob;
  noiseEnvironment: string;
  languageMix: string;
  filename?: string;
  idempotencyKey?: string;
}): Promise<StartTranscriptionResponse> {
  const formData = new FormData();
  formData.append("patient_id", params.patientId);
  formData.append("visit_id", params.visitId);
  formData.append("audio_file", params.audioBlob, params.filename ?? "visit-audio.webm");
  formData.append("noise_environment", params.noiseEnvironment);
  formData.append("language_mix", params.languageMix);

  const response = await apiClient.post("/api/notes/transcribe", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
      ...(params.idempotencyKey ? { "X-Idempotency-Key": params.idempotencyKey } : {}),
    },
  });
  return {
    jobId: String(response.data?.job_id || response.data?.jobId || ""),
    status: String(response.data?.status || "queued") as StartTranscriptionResponse["status"],
    message: String(response.data?.message || ""),
  };
}

export async function pollTranscriptionUntilTerminal(params: {
  patientId: string;
  visitId: string;
  languageMix: string;
  jobId: string;
  maxWaitMs?: number;
  onStatus?: (status: { jobId: string; status: "queued" | "processing" | "timeout"; message?: string }) => void;
}): Promise<PollResult> {
  let lastStatusPayload: unknown = null;
  const startedAt = Date.now();
  let pollInterval = INITIAL_POLL_INTERVAL_MS;
  let transientFailures = 0;

  while (Date.now() - startedAt < (params.maxWaitMs ?? DEFAULT_MAX_WAIT_MS)) {
    await delay(pollInterval);
    try {
      const statusResponse = await apiClient.get(`/api/notes/transcribe/status/${params.patientId}/${params.visitId}`);
      lastStatusPayload = statusResponse.data;
      const payload = statusResponse.data as TranscriptionJobStatusPayload;
      const status = String(payload?.status ?? "") as TranscriptionStatus;
      const jobId = String(payload?.jobId || params.jobId);
      if (status === "failed") {
        throw new TranscriptionJobError(
          String(payload?.errorMessage ?? payload?.message ?? "transcription failed"),
          payload,
        );
      }
      if (status === "completed") {
        try {
          await apiClient.post(`/api/notes/${params.patientId}/visits/${params.visitId}/dialogue/structure`);
        } catch {
          // Structure endpoint can fail if already structured; ignore and continue.
        }
        const dialogueResponse = await apiClient.get(`/api/notes/${params.patientId}/visits/${params.visitId}/dialogue`);
        return {
          kind: "completed",
          result: transcriptionResultFromDialoguePayload(
            dialogueResponse.data,
            params.languageMix,
            `${params.visitId}-transcript`,
          ),
          jobId,
          lastPayload: payload,
        };
      }
      if (status === "queued" || status === "processing" || status === "timeout" || status === "pending") {
        params.onStatus?.({
          jobId,
          status: status === "queued" ? "queued" : status === "timeout" ? "timeout" : "processing",
          message:
            status === "timeout"
              ? "Transcription is still processing in background. You can keep this page open or check again shortly."
              : String(payload?.message || "Transcription in progress"),
        });
      }
      transientFailures = 0;
      pollInterval = Math.min(MAX_POLL_INTERVAL_MS, Math.round(pollInterval * 1.2));
    } catch (error) {
      if (error instanceof TranscriptionJobError) {
        throw error;
      }
      transientFailures += 1;
      pollInterval = Math.min(MAX_POLL_INTERVAL_MS, Math.round(pollInterval * 1.8));
      params.onStatus?.({
        jobId: params.jobId,
        status: "processing",
        message:
          transientFailures > 1
            ? "Network is unstable. Transcription is still processing in background."
            : "Checking transcription status...",
      });
    }
  }

  return {
    kind: "still_processing",
    jobId: params.jobId,
    lastPayload: lastStatusPayload,
    message: "Transcription is still processing. You can keep this page open or check again shortly.",
  };
}

export async function fetchTranscriptionResult(params: {
  patientId: string;
  visitId: string;
  languageMix: string;
}): Promise<TranscriptionResult> {
  const dialogueResponse = await apiClient.get(`/api/notes/${params.patientId}/visits/${params.visitId}/dialogue`);
  return transcriptionResultFromDialoguePayload(
    dialogueResponse.data,
    params.languageMix,
    `${params.visitId}-transcript`,
  );
}
