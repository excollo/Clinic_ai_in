import apiClient from "@/lib/apiClient";
import type { TranscriptionResult, TranscriptionSegment } from "@/api/types";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export class TranscriptionJobError extends Error {
  statusPayload: unknown;

  constructor(message: string, statusPayload: unknown) {
    super(message);
    this.name = "TranscriptionJobError";
    this.statusPayload = statusPayload;
  }
}

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

function adaptDialogueResponse(dialogue: Array<Record<string, string>>, language: string, transcriptId: string): TranscriptionResult {
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

function extractApiErrorMessage(error: unknown): string {
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
}): Promise<TranscriptionResult> {
  const formData = new FormData();
  formData.append("patient_id", params.patientId);
  formData.append("visit_id", params.visitId);
  formData.append("audio_file", params.audioBlob, params.filename ?? "visit-audio.webm");
  formData.append("noise_environment", params.noiseEnvironment);
  formData.append("language_mix", params.languageMix);

  await apiClient.post("/api/notes/transcribe", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  let lastStatusPayload: unknown = null;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await delay(2000);
    const statusResponse = await apiClient.get(`/api/notes/transcribe/status/${params.patientId}/${params.visitId}`);
    lastStatusPayload = statusResponse.data;
    const status = String(statusResponse.data?.status ?? "");
    if (status === "failed") {
      throw new TranscriptionJobError(
        String(statusResponse.data?.error_message ?? statusResponse.data?.message ?? "transcription failed"),
        statusResponse.data,
      );
    }
    if (status === "completed") {
      try {
        await apiClient.post(`/api/notes/${params.patientId}/visits/${params.visitId}/dialogue/structure`);
      } catch {
        // Structure endpoint can fail if already structured; ignore and continue with available dialogue.
      }
      const dialogueResponse = await apiClient.get(`/api/notes/${params.patientId}/visits/${params.visitId}/dialogue`);
      const structured = (dialogueResponse.data?.structured_dialogue ?? []) as Array<Record<string, string>>;
      const transcriptId = String(dialogueResponse.data?.audio_file_path ?? `${params.visitId}-transcript`);
      return adaptDialogueResponse(structured, String(params.languageMix || "en"), transcriptId);
    }
  }
  try {
    const dialogueResponse = await apiClient.get(`/api/notes/${params.patientId}/visits/${params.visitId}/dialogue`);
    const structured = (dialogueResponse.data?.structured_dialogue ?? []) as Array<Record<string, string>>;
    if (structured.length > 0) {
      const transcriptId = String(dialogueResponse.data?.audio_file_path ?? `${params.visitId}-transcript`);
      return adaptDialogueResponse(structured, String(params.languageMix || "en"), transcriptId);
    }
  } catch {
    // Keep throwing the richer timeout error below.
  }
  throw new TranscriptionJobError(
    `Transcription is taking longer than expected. Please retry in a minute. (${extractApiErrorMessage(lastStatusPayload)})`,
    lastStatusPayload,
  );
}
