import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { PatientRecord } from "@/lib/mocks/patients";
import { formatClinicDate } from "@/lib/format";

export default function VisitsTab({ patient }: { patient: PatientRecord }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const visits = Array.from({ length: Math.max(patient.visitCount, 1) }, (_, i) => ({
    id: `vis_${patient.id}_${i}`,
    date: new Date(Date.now() - i * 86400000),
    type: i % 2 === 0 ? t("patientDetail.walkIn") : t("patientDetail.scheduled"),
    diagnosis: i % 2 === 0 ? t("patientDetail.viralFever") : t("patientDetail.htnFollowup"),
    status: i === 0 ? t("patientDetail.done") : t("patientDetail.completed"),
  }));
  return (
    <div className="space-y-2">
      {visits.map((v) => (
        <button key={v.id} onClick={() => navigate(`/visits/${v.id}`)} className="clinic-card w-full p-3 text-left">
          <p className="text-sm font-semibold">{formatClinicDate(v.date)} · {v.type}</p>
          <p className="text-xs text-clinic-muted">{v.diagnosis} · {v.status}</p>
        </button>
      ))}
    </div>
  );
}
