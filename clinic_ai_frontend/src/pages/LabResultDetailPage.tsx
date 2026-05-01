import { useMemo } from "react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import apiClient from "@/lib/apiClient";

type LabQueueDetail = {
  record_id?: string;
  extracted_values?: Array<Record<string, unknown>>;
  flags?: string[];
  status?: string;
};

export default function LabResultDetailPage() {
  const { t } = useTranslation();
  const { labId = "" } = useParams();
  const detailQuery = useQuery({
    queryKey: ["lab-detail", labId],
    enabled: Boolean(labId),
    queryFn: async () => {
      const response = await apiClient.get("/follow-through/lab-queue");
      const items = (response.data?.items ?? []) as LabQueueDetail[];
      return items.find((item) => String(item.record_id || "") === labId) ?? null;
    },
  });
  const lab = detailQuery.data;
  const extractedValues = useMemo(() => {
    const values = Array.isArray(lab?.extracted_values) ? lab.extracted_values : [];
    return values.map((value, idx) => ({
      id: `value_${idx}`,
      test: String(value.test || value.name || `metric_${idx + 1}`),
      value: String(value.value || value.result || "-"),
      unit: String(value.unit || "-"),
      refRange: String(value.ref_range || value.reference || "-"),
      status: String(value.status || (Boolean(value.abnormal) ? "abnormal" : "normal")),
    }));
  }, [lab?.extracted_values]);
  const [sending, setSending] = useState(false);

  if (!lab) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-clinic-muted">
        {!detailQuery.isLoading ? "No lab record found." : "Loading lab record..."}
      </div>
    );
  }

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
            {extractedValues.map((v) => (
              <div key={v.test} className={`grid grid-cols-5 gap-2 py-2 text-sm ${v.status === "abnormal" ? "bg-red-50 text-red-700" : ""}`}>
                <p>{v.test}</p>
                <p>{v.value}</p>
                <p>{v.unit}</p>
                <p>{v.refRange}</p>
                <p className={v.status === "abnormal" ? "text-red-600" : "text-green-600"}>{v.status}</p>
              </div>
            ))}
            {!detailQuery.isLoading && extractedValues.length === 0 && (
              <div className="py-3 text-sm text-clinic-muted">No extracted lab values yet.</div>
            )}
          </div>
        </div>
        <div className="rounded-2xl bg-amber-50 p-4 text-sm">
          <p className="font-semibold">{t("lab.doctorSummary")}</p>
          <p>{Array.isArray(lab.flags) && lab.flags.length > 0 ? lab.flags.join(", ") : "No flagged abnormalities."}</p>
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
