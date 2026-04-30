import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { fetchCareprepQueue } from "@/lib/mocks/careprep";

export default function CarePrepListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [filter, setFilter] = useState("today");
  const query = useQuery({ queryKey: ["careprep-queue"], queryFn: fetchCareprepQueue });

  const rows = useMemo(() => {
    const list = [...(query.data ?? [])];
    return list
      .filter((item) => {
        if (filter === "pending") return !item.reviewed;
        if (filter === "reviewed") return item.reviewed;
        if (filter === "walk_in") return item.visitType === "walk_in";
        if (filter === "scheduled") return item.visitType === "scheduled";
        return true;
      })
      .sort((a, b) => {
        if (a.hasRedFlag !== b.hasRedFlag) return a.hasRedFlag ? -1 : 1;
        if (a.reviewed !== b.reviewed) return a.reviewed ? 1 : -1;
        return a.token.localeCompare(b.token);
      });
  }, [query.data, filter]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("careprep.title")}</h2>
        <p className="text-sm text-clinic-muted">{t("careprep.subtitle")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {[
          ["today", t("careprep.filterToday")],
          ["pending", t("careprep.filterPending")],
          ["reviewed", t("careprep.filterReviewed")],
          ["walk_in", t("careprep.filterWalkIn")],
          ["scheduled", t("careprep.filterScheduled")],
        ].map(([key, label]) => (
          <button key={key} onClick={() => setFilter(key)} className={`rounded-full px-3 py-1 text-xs ${filter === key ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>{label}</button>
        ))}
      </div>
      <div className="clinic-card overflow-hidden">
        {!query.isLoading && rows.length === 0 && (
          <div className="p-10 text-center text-sm text-clinic-muted">{t("careprep.empty")}</div>
        )}
        <div className="divide-y divide-clinic-border">
          {rows.map((row) => (
            <div key={row.visitId} className={`grid grid-cols-1 gap-2 p-3 md:grid-cols-6 ${row.hasRedFlag ? "bg-amber-50" : row.reviewed ? "opacity-60" : ""}`}>
              <div><span className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">{row.token}</span></div>
              <div>
                <p className="font-semibold">{row.patientName}</p>
                <p className="text-xs text-clinic-muted">{row.age} · {row.sex}</p>
              </div>
              <div>{row.hasRedFlag && <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-700"><AlertTriangle className="h-3 w-3" />{t("careprep.redFlag")}</span>}</div>
              <p className="truncate text-sm">{row.chiefComplaint}</p>
              <p className="text-sm text-clinic-muted">{row.questionCount} Q · {row.imageCount} img</p>
              <button onClick={() => navigate(`/careprep/${row.visitId}`)} className="rounded-lg border border-clinic-border bg-white px-3 py-1 text-sm">{row.reviewed ? t("careprep.open") : t("careprep.review")}</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
