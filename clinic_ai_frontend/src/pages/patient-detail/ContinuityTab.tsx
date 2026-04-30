import type { PatientRecord } from "@/lib/mocks/patients";
import { useTranslation } from "react-i18next";

export default function ContinuityTab({ patient }: { patient: PatientRecord }) {
  const { t } = useTranslation();
  if (patient.visitCount < 2) {
    return <div className="clinic-card p-6 text-center text-sm text-clinic-muted">{t("patientDetail.firstVisitEmpty")}</div>;
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <div className="clinic-card p-3"><p className="text-xs text-clinic-muted">{t("patientDetail.lastDiagnosis")}</p><p>{t("patientDetail.lastDiagnosisValue")}</p></div>
      <div className="clinic-card p-3"><p className="text-xs text-clinic-muted">{t("patientDetail.currentMeds")}</p><p>{t("patientDetail.currentMedsValue")}</p></div>
      <div className="clinic-card p-3"><p className="text-xs text-clinic-muted">{t("patientDetail.lastLabs")}</p><p className="text-red-600">{t("patientDetail.lastLabsValue")}</p></div>
      <div className="clinic-card p-3"><p className="text-xs text-clinic-muted">{t("patientDetail.lastAdvice")}</p><p>{t("patientDetail.lastAdviceValue")}</p></div>
    </div>
  );
}
