import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/lib/authStore";
import { fetchCareprepSessions } from "@/lib/services/careprepService";

export default function CarePrepListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const doctorId = useAuthStore((s) => s.doctorId ?? "");
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["careprep-sessions", doctorId],
    enabled: Boolean(doctorId),
    queryFn: () => fetchCareprepSessions(doctorId),
  });

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (query.data ?? [])
      .filter((item) => {
        if (!q) return true;
        return (
          item.patientName.toLowerCase().includes(q) ||
          item.patientId.toLowerCase().includes(q) ||
          item.mobile.toLowerCase().includes(q) ||
          item.token.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
  }, [query.data, search]);

  const openPatientProfile = (patientId: string) => {
    if (!patientId.trim()) return;
    navigate(`/patients/${patientId}`);
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("careprep.title")}</h2>
        <p className="text-sm text-clinic-muted">{t("careprep.subtitle")}</p>
      </div>
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-clinic-muted" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-xl border border-clinic-border bg-white py-2 pl-9 pr-3"
          placeholder={t("careprep.searchPlaceholder")}
        />
      </div>
      <div className="clinic-card overflow-hidden">
        {query.isLoading ? (
          <div className="space-y-3 p-4">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100" />)}</div>
        ) : rows.length === 0 ? (
          <div className="p-10 text-center text-sm text-clinic-muted">{t("careprep.empty")}</div>
        ) : (
          <div className="max-h-[70vh] overflow-auto">
            {rows.map((row) => {
              const initials = row.patientName
                .split(/\s+/)
                .filter(Boolean)
                .map((w) => w[0])
                .slice(0, 2)
                .join("")
                .toUpperCase();
              const updatedLabel =
                row.updatedAt && !Number.isNaN(new Date(row.updatedAt).getTime())
                  ? formatDistanceToNow(new Date(row.updatedAt), { addSuffix: true })
                  : "—";
              return (
                <div
                  key={row.visitId}
                  className="grid grid-cols-1 gap-2 border-b border-clinic-border px-4 py-3 last:border-b-0 md:grid-cols-6 md:items-center"
                >
                  <button
                    type="button"
                    onClick={() => openPatientProfile(row.patientId)}
                    disabled={!row.patientId.trim()}
                    className="flex min-w-0 items-center gap-3 rounded-lg text-left hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 md:col-span-1"
                  >
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
                      {initials || "?"}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{row.patientName}</p>
                      <p className="truncate text-xs text-clinic-muted">{row.patientId || t("common.unknown")}</p>
                    </div>
                  </button>
                  <p className="text-sm md:text-center">
                    <span className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">{row.token || t("careprep.tokenPending")}</span>
                  </p>
                  <p className="truncate text-sm">{row.mobile || "—"}</p>
                  <p className="text-sm text-clinic-muted">
                    {t("careprep.qaCount", { count: row.questionCount })} · {row.intakeStatus}
                  </p>
                  <p className="text-sm text-clinic-muted">{updatedLabel}</p>
                  <div className="md:flex md:justify-end">
                    <button
                      type="button"
                      onClick={() => navigate(`/careprep/${row.visitId}`)}
                      className="w-full rounded-xl border border-clinic-border bg-white px-3 py-2 text-sm md:w-auto"
                    >
                      {t("careprep.openSession")}
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
