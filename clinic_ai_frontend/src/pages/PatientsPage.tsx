import { useEffect, useMemo, useState } from "react";
import { Search, UserRound, QrCode, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { PATIENT_LIST_PAGE_SIZE, usePatients } from "@/features/patients/hooks/usePatients";

export default function PatientsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<string[]>(["all"]);
  const [page, setPage] = useState(0);

  useEffect(() => {
    const id = setTimeout(() => setSearch(query), 300);
    return () => clearTimeout(id);
  }, [query]);

  const filtersKey = useMemo(() => filters.join(","), [filters]);
  useEffect(() => {
    setPage(0);
  }, [search, filtersKey]);

  const patientQuery = usePatients(search, filters, page);
  const rows = patientQuery.data?.data ?? [];
  const total = patientQuery.data?.total ?? 0;
  const hasNextPage = total > 0 && (page + 1) * PATIENT_LIST_PAGE_SIZE < total;
  const rangeStart = total === 0 ? 0 : page * PATIENT_LIST_PAGE_SIZE + 1;
  const rangeEnd = Math.min((page + 1) * PATIENT_LIST_PAGE_SIZE, total);

  const toggleFilter = (key: string) => {
    if (key === "all") return setFilters(["all"]);
    setFilters((prev) => {
      const next = prev.includes(key) ? prev.filter((f) => f !== key) : [...prev.filter((f) => f !== "all"), key];
      return next.length ? next : ["all"];
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-h2">{t("patients.title")}</h2>
          <p className="text-sm text-clinic-muted">{total} total</p>
        </div>
        <div className="flex gap-2">
          <button className="rounded-xl border border-clinic-border bg-white px-4 py-2 text-sm"><QrCode className="mr-1 inline h-4 w-4" />{t("patients.scanAbhaQr")}</button>
          <button onClick={() => navigate("/register-patient")} className="rounded-xl bg-clinic-primary px-4 py-2 text-sm text-white"><Plus className="mr-1 inline h-4 w-4" />{t("patients.registerPatient")}</button>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-clinic-muted" />
        <input value={query} onChange={(e) => setQuery(e.target.value)} className="w-full rounded-xl border border-clinic-border bg-white py-2 pl-9 pr-3" placeholder={t("patients.searchPlaceholder")} />
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          ["all", t("patients.filterAll")],
          ["last30", t("patients.filterLast30")],
          ["chronic", t("patients.filterChronic")],
          ["abha", t("patients.filterAbha")],
        ].map(([key, label]) => (
          <button key={key} onClick={() => toggleFilter(key)} className={`rounded-full px-3 py-1 text-xs ${filters.includes(key) ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white text-clinic-ink"}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="clinic-card overflow-hidden">
        {patientQuery.isLoading ? (
          <div className="space-y-3 p-4">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 animate-pulse rounded-lg bg-slate-100" />)}</div>
        ) : rows.length === 0 ? (
          <div className="grid place-items-center gap-2 p-10 text-center">
            <UserRound className="h-12 w-12 text-slate-300" />
            <p className="text-lg font-semibold">{t("patients.noPatients")}</p>
            <p className="text-sm text-clinic-muted">{t("patients.noPatientsHint")}</p>
            <button onClick={() => navigate("/register-patient")} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("patients.registerFirst")}</button>
          </div>
        ) : (
          <>
            <div className="max-h-[70vh] overflow-auto">
              {rows.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => navigate(`/patients/${p.id}`, { state: { patient: p } })}
                  className="grid w-full grid-cols-1 gap-2 border-b border-clinic-border px-4 py-3 text-left hover:bg-slate-50 md:grid-cols-5"
                >
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">{p.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}</span>
                    <div>
                      <p className="text-sm font-semibold">{p.name}</p>
                      <p className="text-xs text-clinic-muted">{p.age} · {p.sex}</p>
                    </div>
                  </div>
                  <p className="text-sm">{p.mobile}</p>
                  <p className="text-sm">{p.visitCount} {t("patients.visitsSuffix")}</p>
                  <p className="text-sm text-clinic-muted">{formatDistanceToNow(new Date(p.lastSeen), { addSuffix: true })}</p>
                  <div className="flex gap-1">
                    {p.abhaLinked && <span className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">{t("patients.badgeAbha")}</span>}
                    {p.chronic && <span className="rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-700">{t("patients.badgeChronic")}</span>}
                  </div>
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-clinic-border bg-slate-50/80 px-4 py-3">
              <p className="text-xs text-clinic-muted">
                {t("patients.pageRange", { start: rangeStart, end: rangeEnd, total })}
                {patientQuery.isFetching && <span className="ml-2 text-clinic-primary">· {t("common.loading")}</span>}
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page === 0 || patientQuery.isFetching}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="rounded-xl border border-clinic-border bg-white px-4 py-2 text-sm disabled:opacity-50"
                >
                  {t("patients.previousPage")}
                </button>
                <button
                  type="button"
                  disabled={!hasNextPage || patientQuery.isFetching}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-xl border border-clinic-border bg-white px-4 py-2 text-sm disabled:opacity-50"
                >
                  {t("patients.nextPage")}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

    </div>
  );
}
