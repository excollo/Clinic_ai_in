import { useMemo, useState } from "react";
import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FileImage, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/apiClient";

type LabItem = {
  record_id?: string;
  patient_id?: string;
  source?: string;
  status?: string;
  flags?: string[];
  created_at?: string;
  updated_at?: string;
  image_count?: number;
};

export default function LabInboxPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [filter, setFilter] = useState("all");
  const listRef = useRef<HTMLDivElement | null>(null);
  const query = useQuery({
    queryKey: ["lab-queue"],
    queryFn: async () => {
      const response = await apiClient.get("/follow-through/lab-queue");
      return (response.data?.items ?? []) as LabItem[];
    },
  });
  const rows = useMemo(() => {
    const list = (query.data ?? []).map((lab, idx) => {
      const flags = Array.isArray(lab.flags) ? lab.flags : [];
      const source = String(lab.source || "uploaded");
      const status = String(lab.status || "received");
      return {
        id: String(lab.record_id || `lab_${idx}`),
        patientName: String(lab.patient_id || "Patient"),
        reportType: "lab record",
        abnormal: flags.length > 0,
        pendingReview: status !== "doctor_reviewed" && status !== "continuity_updated",
        reviewed: status === "doctor_reviewed" || status === "continuity_updated",
        lowConfidence: false,
        source,
        fileType: Number(lab.image_count || 0) > 0 ? "image" : "pdf",
        receivedAt: String(lab.updated_at || lab.created_at || new Date().toISOString()),
      };
    });
    return [...list]
      .filter((lab) => {
        if (filter === "abnormal") return lab.abnormal;
        if (filter === "pending") return lab.pendingReview;
        if (filter === "reviewed") return lab.reviewed;
        return true;
      })
      .sort((a, b) => Number(b.abnormal) - Number(a.abnormal) || Number(b.pendingReview) - Number(a.pendingReview) || Number(a.reviewed) - Number(b.reviewed));
  }, [filter, query.data]);
  const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => listRef.current, estimateSize: () => 84, overscan: 10 });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("lab.title")}</h2>
        <p className="text-sm text-clinic-muted">{t("lab.subtitle")}</p>
      </div>
      <div className="flex gap-2">
        {[["all", t("lab.filterAll")], ["abnormal", t("lab.filterAbnormal")], ["pending", t("lab.filterPending")], ["reviewed", t("lab.filterReviewed")]].map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)} className={`rounded-full px-3 py-1 text-xs ${filter === k ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>{l}</button>
        ))}
      </div>
      <div ref={listRef} className="clinic-card max-h-[70vh] overflow-auto">
        {!query.isLoading && rows.length === 0 && (
          <div className="p-6 text-sm text-clinic-muted">No lab records available.</div>
        )}
        <div className="relative" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((item) => {
          const lab = rows[item.index];
          return (
          <button key={lab.id} style={{ transform: `translateY(${item.start}px)` }} onClick={() => navigate(`/lab-inbox/${lab.id}`)} className={`absolute left-0 top-0 grid w-full grid-cols-1 gap-2 border-b border-clinic-border p-3 text-left md:grid-cols-6 ${lab.abnormal ? "border-l-4 border-l-red-500" : ""} ${lab.reviewed ? "opacity-70" : ""}`}>
            <div>{lab.fileType === "pdf" ? <FileText className="h-4 w-4" /> : <FileImage className="h-4 w-4" />}</div>
            <div className="md:col-span-2">
              <p className="font-semibold">{lab.patientName}</p>
              <p className="text-xs text-clinic-muted">{lab.reportType}</p>
            </div>
            <div>{lab.abnormal && <span className="rounded-full bg-red-100 px-2 py-1 text-xs text-red-700">{t("lab.abnormal")}</span>} {lab.lowConfidence && <span className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-700">{t("lab.lowConfidence")}</span>}</div>
            <p className="text-sm text-clinic-muted">{lab.source} · {new Date(lab.receivedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
            <div><span className={`rounded-lg px-2 py-1 text-xs ${lab.abnormal ? "bg-red-100 text-red-700" : "bg-slate-100"}`}>{lab.abnormal ? t("lab.review") : t("lab.open")}</span></div>
          </button>
          );
        })}
        </div>
      </div>
    </div>
  );
}
