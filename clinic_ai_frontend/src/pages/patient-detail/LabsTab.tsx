import { formatClinicDate } from "@/lib/format";
import { useTranslation } from "react-i18next";

export default function LabsTab() {
  const { t } = useTranslation();
  const rows = [
    { date: new Date(), test: "CBC", abnormal: true },
    { date: new Date(Date.now() - 86400000), test: "LFT", abnormal: false },
  ];
  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <button key={`${row.test}_${row.date.toISOString()}`} className="clinic-card w-full p-3 text-left">
          <p className="text-sm">{formatClinicDate(row.date)} · {row.test}</p>
          {row.abnormal && <p className="text-xs text-red-600">{t("patientDetail.abnormal")}</p>}
        </button>
      ))}
    </div>
  );
}
