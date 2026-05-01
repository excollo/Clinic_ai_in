import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useVisitStore } from "@/lib/visitStore";
import type { TranscriptionResult } from "@/api/types";
import { TranscriptionJobError, transcribeVisitAudio } from "@/features/visits/hooks/useTranscription";

export default function TranscriptionTab({ onGenerate }: { onGenerate: () => void }) {
  const { t } = useTranslation();
  const visit = useVisitStore();
  const [state, setState] = useState<"idle" | "recording" | "processing" | "done">("idle");
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

  const runTranscription = async (blob: Blob, filename = "visit-audio.webm") => {
    setState("processing");
    setFailedReason(null);
    setLastAudioBlob(blob);
    setLastFilename(filename);
    try {
      const transcription = await transcribeVisitAudio({
        patientId: visit.patientId,
        visitId: visit.visitId,
        audioBlob: blob,
        noiseEnvironment,
        languageMix,
        filename,
      });
      setResult(transcription);
      setState("done");
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Unknown error";
      if (error instanceof TranscriptionJobError) {
        console.error("Transcription failed status payload:", error.statusPayload);
      } else {
        console.error(error);
      }
      setFailedReason(reason);
      toast.error(reason || "Transcript processing failed");
      setState("idle");
    }
  };

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
        Upload/record conversation audio here. Once completed, continue to <span className="font-semibold">Clinical Note.</span>
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
              disabled={!selectedAudioFile || state === "processing"}
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
          {(state === "recording" || state === "processing") && (
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
      {state === "processing" && <p className="mt-2 text-sm text-clinic-muted">{t("transcription.processing")}</p>}
      {failedReason && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p>Transcript processing failed.</p>
          <p className="mt-1">Reason: {failedReason || "Unknown error"}</p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => lastAudioBlob && runTranscription(lastAudioBlob, lastFilename)}
              disabled={!lastAudioBlob || state === "processing"}
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
      {state === "done" && (
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
