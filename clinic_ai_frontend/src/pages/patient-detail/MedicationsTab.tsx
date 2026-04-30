import { useTranslation } from "react-i18next";

export default function MedicationsTab() {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      <div className="clinic-card p-3">{t("patientDetail.med1")}</div>
      <div className="clinic-card p-3">{t("patientDetail.med2")}</div>
    </div>
  );
}
