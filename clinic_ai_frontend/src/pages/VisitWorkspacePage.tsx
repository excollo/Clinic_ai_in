import { lazy, Suspense, useEffect, useMemo } from "react";
import { CheckCircle2, Lock } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useVisitStore, type VisitTabKey } from "@/lib/visitStore";
import apiClient from "@/lib/apiClient";

const PrevisitTab = lazy(() => import("./visit-workspace/PrevisitTab"));
const VitalsTab = lazy(() => import("./visit-workspace/VitalsTab"));
const TranscriptionTab = lazy(() => import("./visit-workspace/TranscriptionTab"));
const ClinicalNoteTab = lazy(() => import("./visit-workspace/ClinicalNoteTab"));
const RecapTab = lazy(() => import("./visit-workspace/RecapTab"));

const tabOrder: VisitTabKey[] = ["previsit", "vitals", "transcription", "clinical_note", "recap"];

export default function VisitWorkspacePage() {
  const { t } = useTranslation();
  const params = useParams();
  const navigate = useNavigate();
  const visit = useVisitStore();
  const queueQuery = useQuery({
    queryKey: ["doctor-queue"],
    queryFn: async () => {
      const doctorId = localStorage.getItem("clinic_doctor_id");
      if (!doctorId) return [];
      const response = await apiClient.get(`/doctor/${doctorId}/queue`);
      return (response.data?.patients ?? []) as Array<Record<string, unknown>>;
    },
    retry: 0,
  });
  const current = useMemo(() => {
    const visitId = params.visitId ?? "";
    const row = (queueQuery.data ?? []).find((item) => String(item.visit_id) === visitId);
    if (!row) return null;
    return {
      visitId,
      patientId: String(row.patient_id ?? ""),
      patientName: String(row.name ?? "patient"),
      patientAge: Number(row.age ?? 0),
      patientSex: String(row.sex ?? "other") as "male" | "female" | "other",
      tokenNumber: String(row.token_number ?? ""),
      visitType: (String(row.visit_type ?? "walk_in") as "walk_in" | "scheduled"),
      status: (String(row.status ?? "in_consult") === "done" ? "done" : "in_consult") as "in_consult" | "done",
      chiefComplaint: String(row.chief_complaint ?? ""),
      patientLanguage: "hindi",
    };
  }, [params.visitId, queueQuery.data]);

  useEffect(() => {
    if (!current) return;
    if (!visit.visitId || visit.visitId !== current.visitId) {
      useVisitStore.getState().setVisit({
        visitId: current.visitId,
        patientId: current.patientId,
        patientName: current.patientName,
        patientAge: current.patientAge,
        patientSex: current.patientSex,
        tokenNumber: current.tokenNumber,
        visitType: current.visitType,
        status: current.status,
        activeTab: "previsit",
        completedTabs: new Set<string>(),
        chiefComplaint: current.chiefComplaint,
      });
    }
  }, [current, visit.visitId]);

  if (!current) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-clinic-muted">
        Visit not found in live queue.
      </div>
    );
  }

  const lockedFrom = tabOrder.findIndex((tab) => !visit.completedTabs.has(tab) && tab !== "previsit");

  const isLocked = (tab: VisitTabKey) => {
    if (tab === "previsit") return false;
    const idx = tabOrder.indexOf(tab);
    const prev = tabOrder[idx - 1];
    return !visit.completedTabs.has(prev);
  };

  const goNext = (tab: VisitTabKey) => {
    const idx = tabOrder.indexOf(tab);
    const next = tabOrder[idx + 1];
    if (next) visit.setActiveTab(next);
  };

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 rounded-2xl border border-clinic-border bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-semibold">{visit.patientName} · {visit.patientAge} · {visit.patientSex}</p>
            <div className="mt-1 flex gap-2 text-xs">
              <span className="rounded-full bg-blue-100 px-2 py-1 text-blue-700">{visit.tokenNumber}</span>
              <span className="rounded-full bg-slate-100 px-2 py-1">{visit.visitType === "walk_in" ? t("visitWorkspace.walkIn") : t("visitWorkspace.scheduled")}</span>
            </div>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs ${visit.status === "done" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{visit.status === "done" ? t("visitWorkspace.done") : t("visitWorkspace.inConsult")}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2" role="tablist" aria-label={t("visitWorkspace.tablistAria")}>
          {tabOrder.map((tab) => {
            const active = tab === visit.activeTab;
            const completed = visit.completedTabs.has(tab);
            const locked = isLocked(tab);
            return (
              <button
                key={tab}
                disabled={locked}
                onClick={() => visit.setActiveTab(tab)}
                role="tab"
                aria-selected={active}
                aria-controls={`tabpanel-${tab}`}
                className={`inline-flex items-center gap-1 rounded-xl px-3 py-2 text-xs ${active ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"} ${locked ? "opacity-50" : ""}`}
              >
                {locked && <Lock className="h-3 w-3" />}
                {completed && <CheckCircle2 className="h-3 w-3" />}
                {t(`visitWorkspace.tab.${tab}`)}
              </button>
            );
          })}
        </div>
      </div>

      <Suspense fallback={<div className="h-24 animate-pulse rounded-xl bg-slate-100" />}>
        {visit.activeTab === "previsit" && <div id="tabpanel-previsit"><PrevisitTab onContinue={() => { visit.markTabComplete("previsit"); goNext("previsit"); }} /></div>}
        {visit.activeTab === "vitals" && <div id="tabpanel-vitals"><VitalsTab onSkip={() => { void import("./visit-workspace/TranscriptionTab"); visit.markTabComplete("vitals"); goNext("vitals"); }} onSaved={() => { void import("./visit-workspace/TranscriptionTab"); visit.markTabComplete("vitals"); goNext("vitals"); }} /></div>}
        {visit.activeTab === "transcription" && <div id="tabpanel-transcription"><TranscriptionTab onGenerate={() => { void import("./visit-workspace/ClinicalNoteTab"); visit.markTabComplete("transcription"); goNext("transcription"); }} /></div>}
        {visit.activeTab === "clinical_note" && <div id="tabpanel-clinical_note"><ClinicalNoteTab onApproved={() => { visit.markTabComplete("clinical_note"); goNext("clinical_note"); }} /></div>}
        {visit.activeTab === "recap" && <div id="tabpanel-recap"><RecapTab approved={visit.completedTabs.has("clinical_note")} /></div>}
      </Suspense>

      {lockedFrom > 0 && <p className="text-xs text-clinic-muted">{t("visitWorkspace.lockedHint")}</p>}
      <div className="hidden">
        <button onClick={() => navigate(`/visits/${visit.visitId}/recap-sent`)}>{t("visitWorkspace.hiddenRouteButton")}</button>
      </div>
    </div>
  );
}
