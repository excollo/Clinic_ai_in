import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import apiClient from "@/lib/apiClient";
import { useVisitStore } from "@/lib/visitStore";
import type { TranscriptionResult } from "@/api/types";
import {
  TranscriptionJobError,
  extractApiErrorMessage,
  fetchTranscriptionResult,
  pollTranscriptionUntilTerminal,
  transcribeVisitAudio,
} from "@/features/visits/hooks/useTranscription";
import {
  initialTranscriptionState,
  transcriptionStateReducer,
} from "@/features/visits/hooks/transcriptionState";

export default function TranscriptionTab({ onGenerate }: { onGenerate: () => void }) {
  const transcriptionStorageKey = "clinic_transcription_active_job";
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const visit = useVisitStore();
  const [model, dispatch] = useReducer(transcriptionStateReducer, initialTranscriptionState);
  const [state, setState] = useState<"idle" | "recording" | "done">("idle");
  const [seconds, setSeconds] = useState(0);
  const [noiseEnvironment, setNoiseEnvironment] = useState("quiet_clinic");
  const [languageMix, setLanguageMix] = useState("hi-en");
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [failedReason, setFailedReason] = useState<string | null>(null);
  const [lastAudioBlob, setLastAudioBlob] = useState<Blob | null>(null);
  const [lastFilename, setLastFilename] = useState<string>("visit-audio.webm");
  const [selectedAudioFile, setSelectedAudioFile] = useState<File | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);
  const startAtRef = useRef<number>(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const workspaceProgressQuery = useQuery({
    queryKey: ["workspace-progress", visit.patientId, visit.visitId],
    queryFn: async () => {
      const response = await apiClient.get(`/patients/${visit.patientId}/visits/${visit.visitId}/workspace-progress`);
      return response.data as { transcription_complete?: boolean };
    },
    enabled: Boolean(visit.patientId && visit.visitId),
    staleTime: 60_000,
  });

  const persistActiveJob = (jobId: string) => {
    localStorage.setItem(
      transcriptionStorageKey,
      JSON.stringify({
        patientId: visit.patientId,
        visitId: visit.visitId,
        jobId,
        languageMix,
        updatedAt: Date.now(),
      }),
    );
  };

  const clearActiveJob = () => localStorage.removeItem(transcriptionStorageKey);

  const computeFileIdempotencyKey = async (blob: Blob) => {
    const bytes = await blob.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", bytes);
    const digest = Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return `transcription:${visit.patientId}:${visit.visitId}:${digest}`;
  };

  const runTranscription = async (blob: Blob, filename = "visit-audio.webm") => {
    dispatch({ type: "start_upload" });
    setFailedReason(null);
    setLastAudioBlob(blob);
    setLastFilename(filename);
    try {
      const idempotencyKey = await computeFileIdempotencyKey(blob);
      const accepted = await transcribeVisitAudio({
        patientId: visit.patientId,
        visitId: visit.visitId,
        audioBlob: blob,
        noiseEnvironment,
        languageMix,
        filename,
        idempotencyKey,
      });
      dispatch({
        type: "job_accepted",
        jobId: accepted.jobId,
        status: accepted.status === "queued" ? "queued" : "processing",
        message: accepted.message,
      });
      persistActiveJob(accepted.jobId);
      const pollResult = await pollTranscriptionUntilTerminal({
        patientId: visit.patientId,
        visitId: visit.visitId,
        languageMix,
        jobId: accepted.jobId,
        onStatus: (status) =>
          dispatch({
            type: "poll_update",
            status: status.status,
            jobId: status.jobId,
            message: status.message,
          }),
      });
      if (pollResult.kind === "completed") {
        setResult(pollResult.result);
        dispatch({ type: "completed" });
        setState("done");
        clearActiveJob();
        void queryClient.invalidateQueries({ queryKey: ["workspace-progress", visit.patientId, visit.visitId] });
      } else {
        dispatch({ type: "poll_update", status: "processing", message: pollResult.message, jobId: pollResult.jobId });
        toast.message(pollResult.message);
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Unknown error";
      if (error instanceof TranscriptionJobError) {
        console.error("Transcription failed status payload:", error.statusPayload);
      } else {
        console.error(error);
      }
      setFailedReason(reason);
      toast.error(reason || "Transcript processing failed");
      dispatch({ type: "failed", error: reason });
      setState("idle");
    }
  };

  useEffect(() => {
    let cancelled = false;
    const resume = async () => {
      const raw = localStorage.getItem(transcriptionStorageKey);
      if (!raw) return;
      try {
        const parsed = JSON.parse(raw) as {
          patientId?: string;
          visitId?: string;
          jobId?: string;
          languageMix?: string;
        };
        if (parsed.patientId !== visit.patientId || parsed.visitId !== visit.visitId || !parsed.jobId) return;
        dispatch({ type: "job_accepted", jobId: parsed.jobId, status: "processing", message: "Resuming transcription status..." });
        const pollResult = await pollTranscriptionUntilTerminal({
          patientId: visit.patientId,
          visitId: visit.visitId,
          languageMix: parsed.languageMix || languageMix,
          jobId: parsed.jobId,
          onStatus: (status) =>
            dispatch({
              type: "poll_update",
              status: status.status,
              jobId: status.jobId,
              message: status.message,
            }),
        });
        if (cancelled) return;
        if (pollResult.kind === "completed") {
          setResult(pollResult.result);
          dispatch({ type: "completed" });
          setState("done");
          clearActiveJob();
          void queryClient.invalidateQueries({ queryKey: ["workspace-progress", visit.patientId, visit.visitId] });
        } else {
          dispatch({ type: "poll_update", status: "processing", message: pollResult.message, jobId: pollResult.jobId });
        }
      } catch (error) {
        if (!cancelled) {
          const message = extractApiErrorMessage(error);
          dispatch({ type: "failed", error: message });
          setFailedReason(message);
        }
      }
    };
    void resume();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visit.patientId, visit.visitId]);

  useEffect(() => {
    if (!workspaceProgressQuery.data?.transcription_complete) return;
    if (model.state === "completed") return;
    let cancelled = false;
    const load = async () => {
      try {
        await apiClient
          .post(`/api/notes/${visit.patientId}/visits/${visit.visitId}/dialogue/structure`)
          .catch(() => undefined);
        const existing = await fetchTranscriptionResult({
          patientId: visit.patientId,
          visitId: visit.visitId,
          languageMix,
        });
        if (cancelled || !existing.segments.length) return;
        setResult(existing);
        dispatch({ type: "completed" });
        setState("done");
        clearActiveJob();
      } catch {
        /* leave UI ready for new recording */
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [
    workspaceProgressQuery.data?.transcription_complete,
    visit.patientId,
    visit.visitId,
    languageMix,
    model.state,
  ]);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        if (timerRef.current) window.clearInterval(timerRef.current);
        try {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          await runTranscription(blob, "visit-audio.webm");
        } finally {
          stream.getTracks().forEach((track) => track.stop());
        }
      };
      mediaRecorderRef.current = recorder;
      startAtRef.current = Date.now();
      recorder.start();
      setState("recording");
      timerRef.current = window.setInterval(() => {
        setSeconds(Math.floor((Date.now() - startAtRef.current) / 1000));
      }, 1000);
    } catch {
      toast.error(t("common.error"));
    }
  };

  const stop = () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  };

  const mmss = useMemo(() => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`, [seconds]);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-clinic-border bg-white px-6 py-4 text-base">
        {workspaceProgressQuery.data?.transcription_complete ? (
          <span>{t("transcription.existingLoaded")}</span>
        ) : (
          <span>
            Upload/record conversation audio here. Once completed, continue to{" "}
            <span className="font-semibold">Clinical Note.</span>
          </span>
        )}
      </div>
      <div className="clinic-card space-y-5 p-6">
        <div>
          <h3 className="text-3xl font-bold text-[#0f1f3d]">Audio Transcription</h3>
          <p className="mt-2 text-2xl text-clinic-muted">Upload an audio file or record audio to generate transcription</p>
        </div>
        <div className="space-y-3">
          <p className="text-2xl font-semibold text-[#0f1f3d]">Upload Audio File</p>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-[280px] flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="rounded-2xl bg-[#e8effa] px-6 py-3 text-2xl font-medium text-[#1f4fa3]"
              >
                Choose File
              </button>
              <span className="text-2xl text-[#4f5d75]">{selectedAudioFile?.name || "No file chosen"}</span>
            </div>
            <button
              type="button"
              disabled={!selectedAudioFile || model.state === "uploading" || model.state === "queued" || model.state === "processing"}
              onClick={() => selectedAudioFile && runTranscription(selectedAudioFile, selectedAudioFile.name)}
              className="rounded-2xl bg-[#79d0a6] px-8 py-3 text-2xl font-semibold text-white disabled:cursor-not-allowed disabled:opacity-70"
            >
              Upload
            </button>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="h-px flex-1 bg-[#d9dfe8]" />
          <span className="text-lg text-[#7b8798]">OR</span>
          <div className="h-px flex-1 bg-[#d9dfe8]" />
        </div>
        <div className="space-y-3">
          <p className="text-2xl font-semibold text-[#0f1f3d]">Record Audio</p>
          {state === "idle" && (
            <button
              type="button"
              onClick={start}
              className="flex w-full items-center justify-center gap-3 rounded-2xl border border-[#b9c8dc] bg-white py-4 text-4xl font-medium text-[#1f3558]"
            >
              Start Recording
            </button>
          )}
          {state === "recording" && (
            <button
              type="button"
              onClick={stop}
              className="flex w-full items-center justify-center gap-3 rounded-2xl border border-red-300 bg-red-50 py-4 text-4xl font-medium text-red-700"
            >
              Stop Recording
            </button>
          )}
          {(state === "recording" || model.state === "uploading" || model.state === "queued" || model.state === "processing") && (
            <p className="text-lg text-clinic-muted">Recording time: {mmss}</p>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <select value={noiseEnvironment} onChange={(e) => setNoiseEnvironment(e.target.value)} className="rounded-xl border border-clinic-border bg-white px-3 py-2">
          <option value="moderate_opd">{t("transcription.noiseStandard")}</option>
          <option value="quiet_clinic">{t("transcription.noiseQuiet")}</option>
          <option value="high_noise">{t("transcription.noiseHigh")}</option>
        </select>
        <select value={languageMix} onChange={(e) => setLanguageMix(e.target.value)} className="rounded-xl border border-clinic-border bg-white px-3 py-2">
          <option value="hi-en">{t("transcription.langHindiEnglish")}</option>
          <option value="en">{t("transcription.langEnglishOnly")}</option>
          <option value="multilingual">{t("transcription.langMultilingual")}</option>
        </select>
      </div>
      {(model.state === "uploading" || model.state === "queued" || model.state === "processing") && (
        <p className="mt-2 text-sm text-clinic-muted">
          {model.message || t("transcription.processing")}
        </p>
      )}
      {failedReason && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p>Transcript processing failed.</p>
          <p className="mt-1">Reason: {failedReason || "Unknown error"}</p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => lastAudioBlob && runTranscription(lastAudioBlob, lastFilename)}
              disabled={!lastAudioBlob || model.state === "uploading" || model.state === "queued" || model.state === "processing"}
              className="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm"
            >
              Upload audio file instead
            </button>
          </div>
        </div>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          setSelectedAudioFile(file);
          event.currentTarget.value = "";
        }}
      />
      <div className="rounded-xl bg-blue-50 p-3 text-sm text-blue-700">{t("transcription.tip")}</div>
      {model.state === "completed" && (
        <div className="clinic-card p-4">
          <div className="mb-3 flex items-center justify-between"><h3 className="font-semibold">{t("transcription.transcript")}</h3><button onClick={onGenerate} className="rounded-xl bg-clinic-primary px-3 py-2 text-sm text-white">{t("transcription.generateClinical")}</button></div>
          <div className="space-y-2">
            {(result?.segments ?? []).map((s, index) => (
              <div key={`${s.speaker}_${index}`} className="rounded-lg border border-clinic-border p-2">
                <p className="text-xs text-clinic-muted">{s.speaker} · {s.timestamp}</p>
                <p className={`text-sm ${s.confidence < 0.7 ? "text-amber-700" : ""}`}>{s.text}</p>
              </div>
            ))}
            <p className="text-xs text-clinic-muted">{t("transcription.confidence")} {Math.round((result?.average_confidence ?? 0) * 100)}%</p>
          </div>
        </div>
      )}
    </div>
  );
}
