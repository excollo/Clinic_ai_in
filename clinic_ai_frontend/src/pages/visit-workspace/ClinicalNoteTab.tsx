import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import apiClient from "@/lib/apiClient";
import type { IndiaClinicalNoteRequest } from "@/api/types";
import { useVisitStore } from "@/lib/visitStore";

type RxItem = { id: string; name: string; dose: string; freq: string; duration: string; food: string };

export default function ClinicalNoteTab({ onApproved }: { onApproved: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const visit = useVisitStore();
  const [approved, setApproved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [assessment, setAssessment] = useState(t("clinicalNote.defaultAssessment"));
  const [plan, setPlan] = useState(t("clinicalNote.defaultPlan"));
  const [followUpDate, setFollowUpDate] = useState("");
  const [followUpInstruction, setFollowUpInstruction] = useState("");
  const [rx, setRx] = useState<RxItem[]>([
    { id: "1", name: t("clinicalNote.defaultRx1Name"), dose: "75mg", freq: t("clinicalNote.freq.once"), duration: t("clinicalNote.defaultRxDuration"), food: t("clinicalNote.food.after") },
    { id: "2", name: t("clinicalNote.defaultRx2Name"), dose: "40mg", freq: t("clinicalNote.freq.once"), duration: t("clinicalNote.defaultRxDuration"), food: t("clinicalNote.food.before") },
  ]);
  const [showAdd, setShowAdd] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const warn = useMemo(() => rx.length >= 2 && !dismissed, [rx.length, dismissed]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const response = await apiClient.get(`/patients/${visit.patientId}/visits/${visit.visitId}/india-clinical-note`);
        const data = response.data as Partial<IndiaClinicalNoteRequest> & { status?: string };
        if (data.assessment) setAssessment(data.assessment);
        if (data.plan) setPlan(data.plan);
        if (Array.isArray(data.rx) && data.rx.length) {
          setRx(
            data.rx.map((item, index) => ({
              id: `${index}`,
              name: item.name,
              dose: item.dose,
              freq: item.frequency,
              duration: item.duration,
              food: item.food_instruction,
            })),
          );
        }
        if (data.follow_up?.date) setFollowUpDate(data.follow_up.date);
        if (data.follow_up?.instruction) setFollowUpInstruction(data.follow_up.instruction);
        const isApproved = data.status === "approved";
        setApproved(isApproved);
        if (isApproved) {
          useVisitStore.getState().markTabComplete("clinical_note");
        }
      } catch {
        // Keep default draft UI when no existing note.
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [visit.patientId, visit.visitId]);

  const buildPayload = (status: "draft" | "approved"): IndiaClinicalNoteRequest => ({
    visit_id: visit.visitId,
    patient_id: visit.patientId,
    assessment,
    plan,
    rx: rx.map((item) => ({
      name: item.name,
      dose: item.dose,
      frequency: item.freq,
      duration: item.duration,
      food_instruction: item.food,
    })),
    investigations: [],
    red_flags: [],
    follow_up: { date: followUpDate || undefined, instruction: followUpInstruction || undefined },
    status,
  });

  const extractErrorMessage = (error: unknown): string => {
    const maybe = error as {
      response?: { data?: { detail?: unknown; message?: unknown } };
      message?: unknown;
    };
    const detail = maybe?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string" && first.msg.trim()) return first.msg;
    }
    if (detail && typeof detail === "object") {
      const nested = detail as { detail?: unknown; message?: unknown; error?: unknown };
      if (typeof nested.detail === "string" && nested.detail.trim()) return nested.detail;
      if (typeof nested.message === "string" && nested.message.trim()) return nested.message;
      if (typeof nested.error === "string" && nested.error.trim()) return nested.error;
    }
    const message = maybe?.response?.data?.message;
    if (typeof message === "string" && message.trim()) return message;
    if (typeof maybe?.message === "string" && maybe.message.trim()) return maybe.message;
    return t("common.error");
  };

  const saveDraft = async () => {
    try {
      setLoading(true);
      await apiClient.post("/notes/india-clinical-note", buildPayload("draft"));
      toast.success(t("clinicalNote.saveDraft"));
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const isDraftMissingError = (error: unknown): boolean => {
    const maybe = error as {
      response?: { status?: number; data?: { detail?: unknown } };
      message?: unknown;
    };
    const status = Number(maybe?.response?.status || 0);
    const detail = maybe?.response?.data?.detail;
    if (status !== 404) return false;
    if (typeof detail === "string") return detail.toLowerCase().includes("draft note not found");
    if (detail && typeof detail === "object") {
      const nested = detail as { detail?: unknown; message?: unknown };
      if (typeof nested.detail === "string" && nested.detail.toLowerCase().includes("draft note not found")) return true;
      if (typeof nested.message === "string" && nested.message.toLowerCase().includes("draft note not found")) return true;
    }
    return false;
  };

  const approve = async () => {
    if (loading || approved) return;
    try {
      setLoading(true);
      try {
        await apiClient.post("/notes/india-clinical-note", buildPayload("approved"));
      } catch (error) {
        if (!isDraftMissingError(error)) throw error;
        // Backend requires an existing draft before approving; create it automatically.
        await apiClient.post("/notes/india-clinical-note", buildPayload("draft"));
        await apiClient.post("/notes/india-clinical-note", buildPayload("approved"));
      }
      setApproved(true);
      await queryClient.invalidateQueries({ queryKey: ["workspace-progress", visit.patientId, visit.visitId] });
      toast.success(t("clinicalNote.approved"));
      onApproved();
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {loading && <div className="h-20 animate-pulse rounded-xl bg-slate-100" />}
      <div>
        <h3 className="text-lg font-semibold">{t("clinicalNote.title")}</h3>
        <p className="text-xs text-clinic-muted">{t("clinicalNote.subtitle")}</p>
        <span className={`mt-2 inline-flex rounded-full px-2 py-1 text-xs ${approved ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{approved ? t("clinicalNote.approved") : t("clinicalNote.draft")}</span>
      </div>
      <div className="rounded-xl bg-slate-100 p-3">
        <p className="mb-1 text-xs font-semibold">{t("clinicalNote.assessment")}</p>
        {approved ? <p>{assessment}</p> : <textarea value={assessment} onChange={(e) => setAssessment(e.target.value)} className="w-full rounded-lg border px-2 py-2" maxLength={500} />}
      </div>
      <div className="rounded-xl bg-slate-100 p-3">
        <p className="mb-1 text-xs font-semibold">{t("clinicalNote.plan")}</p>
        {approved ? <p>{plan}</p> : <textarea value={plan} onChange={(e) => setPlan(e.target.value)} className="w-full rounded-lg border px-2 py-2" maxLength={800} />}
      </div>
      <div className="rounded-xl bg-slate-100 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold">{t("clinicalNote.rx")} ({rx.length})</p>
          {!approved && <button onClick={() => setShowAdd((v) => !v)} className="text-sm text-clinic-primary">{t("clinicalNote.addMedicine")}</button>}
        </div>
        {warn && <div className="mb-2 rounded-lg bg-amber-100 p-2 text-xs text-amber-700">{t("clinicalNote.interactionWarning")} <button onClick={() => setDismissed(true)} className="underline">{t("clinicalNote.acknowledge")}</button></div>}
        <div className="space-y-2">
          {rx.map((item) => (
            <div key={item.id} className="rounded-lg border border-clinic-border bg-white p-2 text-sm">
              <p className="font-semibold">{item.name}</p>
              <p>{item.freq} · {item.duration} · {item.food}</p>
            </div>
          ))}
        </div>
        {showAdd && !approved && (
          <AddMedicineForm
            onSave={(item) => {
              setRx((prev) => [{ id: crypto.randomUUID(), ...item }, ...prev]);
              setShowAdd(false);
              void saveDraft();
            }}
            onCancel={() => setShowAdd(false)}
          />
        )}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-xl bg-red-50 p-3"><p className="text-xs font-semibold">{t("clinicalNote.redFlags")}</p><p className="text-sm">{t("clinicalNote.redFlagsValue")}</p></div>
        <div className="rounded-xl bg-slate-100 p-3">
          <p className="text-xs font-semibold">{t("clinicalNote.followUp")}</p>
          {approved ? (
            <p className="text-sm">{followUpDate || "-"} · {followUpInstruction || t("clinicalNote.followUpValue")}</p>
          ) : (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input type="date" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)} className="rounded-lg border px-2 py-1" />
              <input value={followUpInstruction} onChange={(e) => setFollowUpInstruction(e.target.value)} className="rounded-lg border px-2 py-1" placeholder={t("clinicalNote.followUpValue")} />
            </div>
          )}
        </div>
      </div>
      <div className="flex justify-between">
        <button
          disabled={loading}
          onClick={() => void saveDraft()}
          className="rounded-xl border border-clinic-border px-4 py-2 disabled:opacity-50"
        >
          {loading ? t("common.loading") : t("clinicalNote.saveDraft")}
        </button>
        <button
          disabled={approved || loading}
          onClick={() => void approve()}
          className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? t("common.loading") : t("clinicalNote.approveContinue")}
        </button>
      </div>
    </div>
  );
}

function AddMedicineForm({ onSave, onCancel }: { onSave: (item: { name: string; dose: string; freq: string; duration: string; food: string }) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [dose, setDose] = useState("");
  const [freq, setFreq] = useState(t("clinicalNote.freq.once"));
  const [duration, setDuration] = useState(t("clinicalNote.defaultDuration"));
  const [food, setFood] = useState(t("clinicalNote.food.after"));
  return (
    <div className="mt-3 rounded-lg border border-clinic-border bg-white p-3">
      <div className="mb-2 grid grid-cols-2 gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("clinicalNote.medicinePlaceholder")} className="rounded-lg border px-2 py-1" />
        <input value={dose} onChange={(e) => setDose(e.target.value)} placeholder="Dose" className="rounded-lg border px-2 py-1" />
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        <select value={freq} onChange={(e) => setFreq(e.target.value)} className="rounded-lg border px-2 py-1"><option>{t("clinicalNote.freq.once")}</option><option>{t("clinicalNote.freq.twice")}</option><option>{t("clinicalNote.freq.thrice")}</option><option>{t("clinicalNote.freq.asNeeded")}</option></select>
        <input value={duration} onChange={(e) => setDuration(e.target.value)} className="rounded-lg border px-2 py-1" />
        <select value={food} onChange={(e) => setFood(e.target.value)} className="rounded-lg border px-2 py-1"><option>{t("clinicalNote.food.before")}</option><option>{t("clinicalNote.food.after")}</option><option>{t("clinicalNote.food.with")}</option><option>{t("clinicalNote.food.empty")}</option></select>
      </div>
      <div className="mt-2 flex justify-end gap-2">
        <button onClick={onCancel} className="rounded-lg border px-3 py-1">{t("clinicalNote.cancel")}</button>
        <button onClick={() => name.trim() && dose.trim() && onSave({ name, dose, freq, duration, food })} className="rounded-lg bg-clinic-primary px-3 py-1 text-white">{t("clinicalNote.save")}</button>
      </div>
    </div>
  );
}
