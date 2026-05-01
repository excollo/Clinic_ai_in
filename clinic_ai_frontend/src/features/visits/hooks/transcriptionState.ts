export type TranscriptionUiState =
  | "idle"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export type TranscriptionStateModel = {
  state: TranscriptionUiState;
  jobId: string | null;
  message: string | null;
  error: string | null;
};

export type TranscriptionAction =
  | { type: "start_upload" }
  | { type: "job_accepted"; jobId: string; status: "queued" | "processing" | "timeout"; message?: string }
  | { type: "poll_update"; status: "queued" | "processing" | "timeout"; message?: string; jobId?: string }
  | { type: "completed"; message?: string }
  | { type: "failed"; error: string }
  | { type: "reset" };

export const initialTranscriptionState: TranscriptionStateModel = {
  state: "idle",
  jobId: null,
  message: null,
  error: null,
};

export function transcriptionStateReducer(
  prev: TranscriptionStateModel,
  action: TranscriptionAction,
): TranscriptionStateModel {
  if (action.type === "start_upload") {
    return { ...prev, state: "uploading", error: null, message: null };
  }
  if (action.type === "job_accepted") {
    return {
      ...prev,
      state: action.status === "queued" ? "queued" : "processing",
      jobId: action.jobId,
      message: action.message || null,
      error: null,
    };
  }
  if (action.type === "poll_update") {
    return {
      ...prev,
      state: action.status === "queued" ? "queued" : "processing",
      jobId: action.jobId ?? prev.jobId,
      message: action.message || prev.message,
      error: null,
    };
  }
  if (action.type === "completed") {
    return { ...prev, state: "completed", message: action.message || null, error: null };
  }
  if (action.type === "failed") {
    return { ...prev, state: "failed", error: action.error, message: null };
  }
  return initialTranscriptionState;
}
