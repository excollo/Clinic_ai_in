import { useMemo } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { getLabById } from "@/lib/mocks/labs";
import { toast } from "sonner";

export default function LabResultDetailPage() {
  const { t } = useTranslation();
  const { labId = "" } = useParams();
  const lab = useMemo(() => getLabById(labId), [labId]);
  const [sending, setSending] = useState(false);
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="min-h-[70vh] rounded-2xl border border-clinic-border bg-white p-4">
        <p className="mb-2 text-sm font-semibold">{t("lab.originalDocument")}</p>
        <div className="h-[60vh] rounded-xl bg-slate-100" />
      </div>
      <div className="space-y-4">
        <div className="rounded-2xl border border-clinic-border bg-white p-4">
          <p className="mb-2 text-sm font-semibold">{t("lab.extractedValues")}</p>
          <div className="divide-y">
            {lab.values.map((v) => (
              <div key={v.test} className={`grid grid-cols-5 gap-2 py-2 text-sm ${v.status === "abnormal" ? "bg-red-50 text-red-700" : ""}`}>
                <p>{v.test}</p>
                <p>{v.value}</p>
                <p>{v.unit}</p>
                <p>{v.refRange}</p>
                <p className={v.status === "abnormal" ? "text-red-600" : "text-green-600"}>{v.status}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm">
          <p className="font-semibold">{t("lab.doctorSummary")}</p>
          <p>Elevated HbA1c and LDL indicate poor glycemic and lipid control. Correlate clinically and optimize therapy.</p>
        </div>
        <div className="rounded-2xl bg-blue-50 p-4 text-sm">
          <p className="font-semibold">{t("lab.patientExplanation")}</p>
          <p>Your sugar and cholesterol are higher than ideal. Please continue medicines and follow diet guidance.</p>
        </div>
        <div className="flex justify-end gap-2">
          <button className="rounded-xl border border-clinic-border px-4 py-2">{t("lab.markReviewed")}</button>
          <button
            disabled={sending}
            onClick={async () => {
              setSending(true);
              await new Promise((r) => setTimeout(r, 1200));
              setSending(false);
              toast.success(t("lab.sentSuccess"));
            }}
            className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50"
          >
            {sending ? t("lab.sending") : t("lab.sendToPatient")}
          </button>
        </div>
      </div>
    </div>
  );
}
