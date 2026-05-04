import { lazy, Suspense, useEffect, useMemo, useRef } from "react";
import { CheckCircle2, Lock } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useVisitStore, workspaceTabOrder, type VisitTabKey } from "@/lib/visitStore";
import apiClient from "@/lib/apiClient";

const PrevisitTab = lazy(() => import("./visit-workspace/PrevisitTab"));
const VitalsTab = lazy(() => import("./visit-workspace/VitalsTab"));
const TranscriptionTab = lazy(() => import("./visit-workspace/TranscriptionTab"));
const ClinicalNoteTab = lazy(() => import("./visit-workspace/ClinicalNoteTab"));
const RecapTab = lazy(() => import("./visit-workspace/RecapTab"));

function normalizeSex(value: unknown): "male" | "female" | "other" {
  const sex = String(value || "").toLowerCase();
  if (sex === "male" || sex === "m") return "male";
  if (sex === "female" || sex === "f") return "female";
  return "other";
}

function normalizeVisitType(value: unknown): "walk_in" | "scheduled" {
  return String(value || "").toLowerCase() === "scheduled" ? "scheduled" : "walk_in";
}

function ageFromDob(dateOfBirth: unknown): number {
  const raw = String(dateOfBirth || "");
  const year = Number(raw.slice(0, 4));
  if (!Number.isFinite(year) || year < 1900) return 0;
  return Math.max(0, new Date().getFullYear() - year);
}

type WorkspaceProgress = {
  vitals_recorded?: boolean;
  transcription_complete?: boolean;
  clinical_note_status?: string | null;
  recap_sent?: boolean;
};

function deriveServerCompletedTabs(
  d: WorkspaceProgress,
  visitType: "walk_in" | "scheduled",
): VisitTabKey[] {
  const has =
    d.vitals_recorded ||
    d.transcription_complete ||
    Boolean(d.clinical_note_status) ||
    Boolean(d.recap_sent);
  if (!has) return [];

  const s = new Set<VisitTabKey>();
  if (visitType === "scheduled") {
    s.add("previsit");
  }
  if (d.vitals_recorded) s.add("vitals");

  const pastWithoutSavedVitals =
    d.transcription_complete || Boolean(d.clinical_note_status) || Boolean(d.recap_sent);
  if (pastWithoutSavedVitals && !d.vitals_recorded) s.add("vitals");

  if (
    d.transcription_complete ||
    d.clinical_note_status === "draft" ||
    d.clinical_note_status === "approved" ||
    d.recap_sent
  )
    s.add("transcription");
  if (d.clinical_note_status === "approved" || d.recap_sent) s.add("clinical_note");
  if (d.recap_sent) s.add("recap");

  return Array.from(s);
}

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
  const workspaceHydratedKeyRef = useRef<string>("");
  const visitId = params.visitId ?? "";
  useEffect(() => {
    workspaceHydratedKeyRef.current = "";
  }, [visitId]);
  const visitDetailQuery = useQuery({
    queryKey: ["visit-detail", visitId],
    enabled: Boolean(visitId),
    queryFn: async () => {
      const response = await apiClient.get(`/api/visits/${visitId}`);
      return response.data as {
        id?: string;
        patient_id?: string;
        status?: string;
        visit_type?: string;
        chief_complaint?: string;
        patient?: {
          first_name?: string;
          last_name?: string;
          date_of_birth?: string;
          gender?: string;
        };
      };
    },
    retry: 0,
  });
  const current = useMemo(() => {
    const row = (queueQuery.data ?? []).find((item) => String(item.visit_id) === visitId);
    if (row) {
      return {
        visitId,
        patientId: String(row.patient_id ?? ""),
        patientName: String(row.name ?? "patient"),
        patientAge: Number(row.age ?? 0),
        patientSex: normalizeSex(row.sex),
        tokenNumber: String(row.token_number ?? ""),
        visitType: normalizeVisitType(row.visit_type),
        status: (String(row.status ?? "in_consult") === "done" ? "done" : "in_consult") as "in_consult" | "done",
        chiefComplaint: String(row.chief_complaint ?? ""),
        patientLanguage: "hindi",
      };
    }

    const detail = visitDetailQuery.data;
    if (!detail) return null;
    const fullName = [detail.patient?.first_name, detail.patient?.last_name].filter(Boolean).join(" ").trim();
    return {
      visitId: String(detail.id || visitId),
      patientId: String(detail.patient_id || ""),
      patientName: fullName || "patient",
      patientAge: ageFromDob(detail.patient?.date_of_birth),
      patientSex: normalizeSex(detail.patient?.gender),
      tokenNumber: "-",
      visitType: normalizeVisitType(detail.visit_type),
      status: (String(detail.status || "in_consult").toLowerCase() === "done" ? "done" : "in_consult") as "in_consult" | "done",
      chiefComplaint: String(detail.chief_complaint || ""),
      patientLanguage: "hindi",
    };
  }, [queueQuery.data, visitDetailQuery.data, visitId]);

  const workspaceProgressQuery = useQuery({
    queryKey: ["workspace-progress", current?.patientId ?? "", current?.visitId ?? ""],
    enabled: Boolean(current?.patientId && current?.visitId),
    queryFn: async () => {
      const response = await apiClient.get(
        `/patients/${current!.patientId}/visits/${current!.visitId}/workspace-progress`,
      );
      return response.data as WorkspaceProgress;
    },
    staleTime: 60_000,
  });

  /** Safe before `current` exists: fallback only until visit header loads */
  const tabOrder = useMemo(
    () => workspaceTabOrder((current?.visitType ?? "walk_in") as "walk_in" | "scheduled"),
    [current?.visitType],
  );

  useEffect(() => {
    if (!current) return;
    if (!visit.visitId || visit.visitId !== current.visitId) return;
    if (visit.visitType !== "walk_in") return;
    const orderForWalkIn = workspaceTabOrder("walk_in");
    if (!orderForWalkIn.includes(visit.activeTab)) {
      useVisitStore.getState().setActiveTab("vitals");
    }
  }, [current, visit.visitId, visit.visitType, visit.activeTab]);

  useEffect(() => {
    if (!current) return;
    const store = useVisitStore.getState();
    const sameVisit = store.visitId === current.visitId;
    const needsFullInit = !store.visitId || !sameVisit;

    if (needsFullInit) {
      store.setVisit({
        visitId: current.visitId,
        patientId: current.patientId,
        patientName: current.patientName,
        patientAge: current.patientAge,
        patientSex: current.patientSex,
        tokenNumber: current.tokenNumber,
        visitType: current.visitType,
        status: current.status,
        activeTab: current.visitType === "walk_in" ? "vitals" : "previsit",
        completedTabs: new Set<string>(),
        chiefComplaint: current.chiefComplaint,
      });
      return;
    }

    if (store.chiefComplaint !== current.chiefComplaint) {
      useVisitStore.setState({ chiefComplaint: current.chiefComplaint });
    }
  }, [current, visit.visitId]);

  useEffect(() => {
    if (!current?.patientId || workspaceProgressQuery.isError || !workspaceProgressQuery.data) return;
    const key = `${current.visitId}:${current.patientId}`;
    if (workspaceHydratedKeyRef.current === key) return;
    const tabs = deriveServerCompletedTabs(workspaceProgressQuery.data, current.visitType);
    if (!tabs.length) return;
    workspaceHydratedKeyRef.current = key;
    useVisitStore.getState().hydrateServerProgress(tabs);
  }, [
    current?.patientId,
    current?.visitId,
    current?.visitType,
    workspaceProgressQuery.data,
    workspaceProgressQuery.isError,
  ]);

  const isLocked = (tab: VisitTabKey) => {
    const idx = tabOrder.indexOf(tab);
    if (idx <= 0) return false;
    const prev = tabOrder[idx - 1];
    return !visit.completedTabs.has(prev);
  };

  if (!current) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-clinic-muted">
        {queueQuery.isLoading || visitDetailQuery.isLoading ? t("common.loading") : "Visit not found."}
      </div>
    );
  }

  const lockedHintVisible = tabOrder.some((tab) => isLocked(tab));

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
        {visit.visitType === "scheduled" && visit.activeTab === "previsit" && (
          <div id="tabpanel-previsit">
            <PrevisitTab onContinue={() => { visit.markTabComplete("previsit"); goNext("previsit"); }} />
          </div>
        )}
        {visit.activeTab === "vitals" && <div id="tabpanel-vitals"><VitalsTab onSkip={() => { void import("./visit-workspace/TranscriptionTab"); visit.markTabComplete("vitals"); goNext("vitals"); }} onSaved={() => { void import("./visit-workspace/TranscriptionTab"); visit.markTabComplete("vitals"); goNext("vitals"); }} /></div>}
        {visit.activeTab === "transcription" && <div id="tabpanel-transcription"><TranscriptionTab onGenerate={() => { void import("./visit-workspace/ClinicalNoteTab"); visit.markTabComplete("transcription"); goNext("transcription"); }} /></div>}
        {visit.activeTab === "clinical_note" && <div id="tabpanel-clinical_note"><ClinicalNoteTab onApproved={() => { visit.markTabComplete("clinical_note"); goNext("clinical_note"); }} /></div>}
        {visit.activeTab === "recap" && <div id="tabpanel-recap"><RecapTab approved={visit.completedTabs.has("clinical_note")} /></div>}
      </Suspense>

      {lockedHintVisible && <p className="text-xs text-clinic-muted">{t("visitWorkspace.lockedHint")}</p>}
      <div className="hidden">
        <button onClick={() => navigate(`/visits/${visit.visitId}/recap-sent`)}>{t("visitWorkspace.hiddenRouteButton")}</button>
      </div>
    </div>
  );
}
