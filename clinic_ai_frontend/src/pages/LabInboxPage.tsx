import { useMemo, useState } from "react";
import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FileImage, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { mockLabs } from "@/lib/mocks/labs";

export default function LabInboxPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [filter, setFilter] = useState("all");
  const listRef = useRef<HTMLDivElement | null>(null);
  const rows = useMemo(() => {
    const large = Array.from({ length: 120 }).map((_, i) => ({ ...mockLabs[i % mockLabs.length], id: `${mockLabs[i % mockLabs.length].id}_${i}` }));
    return [...large]
      .filter((lab) => {
        if (filter === "abnormal") return lab.abnormal;
        if (filter === "pending") return lab.pendingReview;
        if (filter === "reviewed") return lab.reviewed;
        return true;
      })
      .sort((a, b) => Number(b.abnormal) - Number(a.abnormal) || Number(b.pendingReview) - Number(a.pendingReview) || Number(a.reviewed) - Number(b.reviewed));
  }, [filter]);
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
        <div className="relative" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((item) => {
          const lab = rows[item.index];
          return (
          <button key={lab.id} style={{ transform: `translateY(${item.start}px)` }} onClick={() => navigate(`/lab-inbox/${lab.id.split("_")[0]}`)} className={`absolute left-0 top-0 grid w-full grid-cols-1 gap-2 border-b border-clinic-border p-3 text-left md:grid-cols-6 ${lab.abnormal ? "border-l-4 border-l-red-500" : ""} ${lab.reviewed ? "opacity-70" : ""}`}>
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
