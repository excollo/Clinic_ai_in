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
      const reason = error instanceof TranscriptionJobError ? error.message : "Unknown error";
      if (error instanceof TranscriptionJobError) {
        console.error("Transcription failed status payload:", error.statusPayload);
      } else {
        console.error(error);
      }
      setFailedReason(reason);
      toast.error("Transcript processing failed");
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
      <div className="clinic-card p-6 text-center">
        {state === "idle" && <button onClick={start} className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-red-500 text-white">{t("transcription.record")}</button>}
        {state === "recording" && <button onClick={stop} className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-red-700 text-white">{t("transcription.stop")}</button>}
        {(state === "recording" || state === "processing") && <p className="mt-3 text-sm">{mmss}</p>}
        {(state === "recording" || state === "processing") && <div className="mx-auto mt-3 flex w-40 items-end justify-center gap-1">{Array.from({ length: 7 }).map((_, i) => <span key={i} className="h-6 w-1 animate-pulse rounded bg-indigo-400" />)}</div>}
        {state === "processing" && <p className="mt-2 text-sm text-clinic-muted">{t("transcription.processing")}</p>}
      </div>
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
      <button type="button" onClick={() => fileInputRef.current?.click()} className="text-sm text-clinic-primary">{t("transcription.uploadAudio")}</button>
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          void runTranscription(file, file.name);
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
