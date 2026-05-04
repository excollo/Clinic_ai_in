import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/lib/authStore";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { fetchPatientsPageReal } from "@/features/patients/hooks/usePatients";
import apiClient from "@/lib/apiClient";

type QueueItem = {
  patient_id: string;
  visit_id: string;
  token_number: string;
  name: string;
  status: string;
};

export default function DashboardPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  useDocumentTitle(`Dashboard · ${t("common.brand")}`);
  const doctorId = useAuthStore((s) => s.doctorId);
  const doctorName = useAuthStore((s) => s.doctorName ?? t("common.doctor"));
  const queueQuery = useQuery({
    queryKey: ["doctor-queue", doctorId],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await apiClient.get(`/doctor/${doctorId}/queue`);
      return response.data as {
        patients: QueueItem[];
        total_today: number;
        in_consult: number;
        done: number;
      };
    },
  });

  useEffect(() => {
    void queryClient.prefetchQuery({
      queryKey: ["recent-patients"],
      queryFn: () => fetchPatientsPageReal({ offset: 0, limit: 20, search: "", filters: ["all"] }),
    });
  }, [queryClient]);

  const queueRows = queueQuery.data?.patients ?? [];

  const statusChipClass = (status: string) => {
    const s = status.toLowerCase();
    if (s === "in_consult") return "bg-amber-100 text-amber-700";
    if (s === "done" || s === "completed") return "bg-emerald-100 text-emerald-700";
    return "bg-blue-100 text-blue-700";
  };

  return (
    <>
      <div className="mb-5 clinic-card p-5">
        <p className="text-xl font-semibold">{t("dashboard.goodMorning", { name: doctorName })}</p>
        <p className="text-sm text-clinic-muted">
          {queueQuery.data
            ? `${queueQuery.data.total_today} today · ${queueQuery.data.in_consult} in consult · ${queueQuery.data.done} done`
            : t("dashboard.queueSummary")}
        </p>
      </div>
      <div className="mb-5 flex gap-3">
        <Link to="/register-patient" className="rounded-xl bg-clinic-primary px-5 py-3 text-sm font-semibold text-white">{t("dashboard.registerPatient")}</Link>
        <Link to="/today-queue" className="rounded-xl border border-clinic-border bg-white px-5 py-3 text-sm font-semibold text-clinic-ink">{t("dashboard.openQueue")}</Link>
      </div>
      <div className="clinic-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <Link to="/today-queue" className="text-sm font-semibold text-clinic-primary hover:underline">
            Today&apos;s Queue
          </Link>
          {queueQuery.isFetching && <p className="text-xs text-clinic-muted">Refreshing...</p>}
        </div>
        {queueRows.length === 0 ? (
          <p className="text-sm text-clinic-muted">No active patients in queue.</p>
        ) : (
          <div className="space-y-2">
            {queueRows.map((row) => (
              <Link
                key={row.visit_id}
                to={`/visits/${row.visit_id}`}
                className="flex items-center justify-between rounded-lg border border-clinic-border px-3 py-2 transition-colors hover:border-clinic-primary/35 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinic-primary focus-visible:ring-offset-2"
                aria-label={`Open visit for ${row.name || row.patient_id}`}
              >
                <div className="min-w-0 pr-3">
                  <p className="truncate text-sm font-medium">{row.name || row.patient_id}</p>
                  <p className="text-xs text-clinic-muted">{row.token_number || "Token pending"}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-1 text-xs capitalize ${statusChipClass(row.status)}`}>
                  {row.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
