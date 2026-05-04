import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/lib/authStore";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import apiClient from "@/lib/apiClient";

export type TodayVisitRow = {
  patient_id: string;
  visit_id: string;
  token_number: string;
  name: string;
  age?: number | null;
  sex?: string | null;
  chief_complaint?: string;
  status: string;
  visit_type?: string;
};

type TodayQueueResponse = {
  patients: TodayVisitRow[];
  total_today: number;
  in_consult: number;
  done: number;
};

function statusChipClass(status: string) {
  const s = status.toLowerCase();
  if (s === "in_consult") return "bg-amber-100 text-amber-700";
  if (s === "done" || s === "completed") return "bg-emerald-100 text-emerald-700";
  return "bg-blue-100 text-blue-700";
}

export default function TodayQueuePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const doctorId = useAuthStore((s) => s.doctorId ?? "");
  useDocumentTitle(`${t("todayQueue.title")} · ${t("common.brand")}`);

  const queueQuery = useQuery({
    queryKey: ["doctor-queue", doctorId, "include-completed"],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await apiClient.get(`/doctor/${doctorId}/queue`, {
        params: { include_completed: true },
      });
      return response.data as TodayQueueResponse;
    },
  });

  const rows = queueQuery.data?.patients ?? [];
  const totalToday = queueQuery.data?.total_today ?? 0;
  const inConsult = queueQuery.data?.in_consult ?? 0;
  const done = queueQuery.data?.done ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-h2">{t("todayQueue.title")}</h2>
          <p className="text-sm text-clinic-muted">{t("todayQueue.subtitle")}</p>
          {queueQuery.data && (
            <p className="mt-1 text-xs text-clinic-muted">
              {t("todayQueue.statsLine", { total: totalToday, inConsult, done })}
            </p>
          )}
        </div>
        <Link to="/patients" className="rounded-xl border border-clinic-border bg-white px-4 py-2 text-sm font-medium text-clinic-ink">
          {t("todayQueue.allPatients")}
        </Link>
      </div>

      <div className="clinic-card overflow-hidden">
        {queueQuery.isLoading ? (
          <div className="space-y-3 p-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100" />)}</div>
        ) : queueQuery.isError ? (
          <div className="p-8 text-center text-sm text-red-600">{t("common.error")}</div>
        ) : rows.length === 0 ? (
          <div className="p-10 text-center text-sm text-clinic-muted">{t("todayQueue.empty")}</div>
        ) : (
          <div className="max-h-[75vh] overflow-auto">
            {rows.map((row) => {
              const initials = String(row.name || "?")
                .split(/\s+/)
                .filter(Boolean)
                .map((w) => w[0])
                .slice(0, 2)
                .join("")
                .toUpperCase();
              const agePart =
                row.age != null && Number.isFinite(Number(row.age)) ? String(row.age) : "";
              const sexPart = row.sex ? String(row.sex) : "";
              const ageSex = [agePart, sexPart].filter(Boolean).join(" · ");
              const visitType = String(row.visit_type || "").toLowerCase();
              const visitLabel =
                visitType === "scheduled" ? t("visitWorkspace.scheduled") : t("visitWorkspace.walkIn");
              return (
                <div
                  key={row.visit_id}
                  className="grid grid-cols-1 gap-3 border-b border-clinic-border px-4 py-3 last:border-b-0 md:grid-cols-[1fr_auto_auto_auto]"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
                      {initials || "?"}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{row.name || row.patient_id}</p>
                      {ageSex ? <p className="text-xs text-clinic-muted">{ageSex}</p> : null}
                      {row.chief_complaint ? (
                        <p className="mt-1 truncate text-xs text-clinic-muted">
                          {t("todayQueue.chiefComplaint")}: {row.chief_complaint}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 md:justify-center">
                    <span className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">{row.token_number || t("careprep.tokenPending")}</span>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">{visitLabel}</span>
                    <span className={`rounded-full px-2 py-1 text-xs ${statusChipClass(row.status)}`}>{row.status}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 md:justify-end">
                    <Link
                      to={`/patients/${row.patient_id}`}
                      className="rounded-xl border border-clinic-border bg-white px-3 py-2 text-center text-sm"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {t("todayQueue.patientProfile")}
                    </Link>
                    <button
                      type="button"
                      onClick={() => navigate(`/visits/${row.visit_id}`)}
                      className="rounded-xl bg-clinic-primary px-3 py-2 text-sm text-white"
                    >
                      {t("todayQueue.openVisit")}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
