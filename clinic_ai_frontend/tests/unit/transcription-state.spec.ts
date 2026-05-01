import { test, expect } from "@playwright/test";
import {
  initialTranscriptionState,
  transcriptionStateReducer,
} from "../../src/features/visits/hooks/transcriptionState";

test("transcription state transitions from upload to completed", async () => {
  const started = transcriptionStateReducer(initialTranscriptionState, { type: "start_upload" });
  const accepted = transcriptionStateReducer(started, {
    type: "job_accepted",
    jobId: "job-1",
    status: "queued",
    message: "Queued",
  });
  const processing = transcriptionStateReducer(accepted, {
    type: "poll_update",
    status: "processing",
    message: "In progress",
  });
  const completed = transcriptionStateReducer(processing, { type: "completed" });

  expect(started.state).toBe("uploading");
  expect(accepted.state).toBe("queued");
  expect(accepted.jobId).toBe("job-1");
  expect(processing.state).toBe("processing");
  expect(completed.state).toBe("completed");
});

test("transcription timeout stays non-failed", async () => {
  const accepted = transcriptionStateReducer(initialTranscriptionState, {
    type: "job_accepted",
    jobId: "job-2",
    status: "processing",
  });
  const timeoutLike = transcriptionStateReducer(accepted, {
    type: "poll_update",
    status: "timeout",
    message: "Still processing in background",
  });

  expect(timeoutLike.state).toBe("processing");
  expect(timeoutLike.error).toBeNull();
  expect(timeoutLike.message).toContain("Still processing");
});
