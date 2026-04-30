import { lazy, Suspense, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useParams } from "react-router-dom";
import { mockPatients } from "@/lib/mocks/patients";

const OverviewTab = lazy(() => import("./patient-detail/OverviewTab"));
const VisitsTab = lazy(() => import("./patient-detail/VisitsTab"));
const ContinuityTab = lazy(() => import("./patient-detail/ContinuityTab"));
const MedicationsTab = lazy(() => import("./patient-detail/MedicationsTab"));
const LabsTab = lazy(() => import("./patient-detail/LabsTab"));

const tabs = ["overview", "visits", "continuity", "medications", "labs"] as const;
type TabKey = (typeof tabs)[number];

export default function PatientDetailPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>("overview");
  const params = useParams();
  const state = useLocation().state as { patient?: (typeof mockPatients)[number] } | undefined;
  const patient = useMemo(() => state?.patient ?? mockPatients.find((p) => p.id === params.id) ?? mockPatients[0], [params.id, state]);

  return (
    <div className="space-y-4">
      <h2 className="text-h2">{patient.name}</h2>
      <div className="flex flex-wrap gap-2">
        {tabs.map((tabKey) => (
          <button key={tabKey} onClick={() => setTab(tabKey)} className={`rounded-xl px-3 py-2 text-sm ${tab === tabKey ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>
            {t(`patientDetail.${tabKey}`)}
          </button>
        ))}
      </div>
      <Suspense fallback={<div className="h-24 animate-pulse rounded-xl bg-slate-100" />}>
        {tab === "overview" && <OverviewTab patient={patient} />}
        {tab === "visits" && <VisitsTab patient={patient} />}
        {tab === "continuity" && <ContinuityTab patient={patient} />}
        {tab === "medications" && <MedicationsTab />}
        {tab === "labs" && <LabsTab />}
      </Suspense>
    </div>
  );
}
