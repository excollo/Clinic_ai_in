import type { PatientRecord } from "@/lib/mocks/patients";
import { useTranslation } from "react-i18next";

export default function OverviewTab({ patient }: { patient: PatientRecord }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-indigo-100 text-lg font-semibold text-indigo-700">{patient.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}</span>
        <div>
          <p className="text-lg font-semibold">{patient.name}</p>
          <p className="text-sm text-clinic-muted">{patient.age} · {patient.sex}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="clinic-card p-3">{t("patientDetail.totalVisits")}: {patient.visitCount}</div>
        <div className="clinic-card p-3">{t("patientDetail.lastConsentVersion")}: v1.2</div>
      </div>
    </div>
  );
}
