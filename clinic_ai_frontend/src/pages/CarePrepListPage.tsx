import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
          item.mobile.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => (a.updatedAt || "").localeCompare(b.updatedAt || "") * -1);
  }, [query.data, search]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("careprep.title")}</h2>
        <p className="text-sm text-clinic-muted">Search and open intake sessions only.</p>
      </div>
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full rounded-xl border border-clinic-border bg-white px-3 py-2"
        placeholder="Search by name, patient ID, or mobile number"
      />
      <div className="clinic-card overflow-hidden">
        {!query.isLoading && rows.length === 0 && (
          <div className="p-10 text-center text-sm text-clinic-muted">{t("careprep.empty")}</div>
        )}
        <div className="divide-y divide-clinic-border">
          {rows.map((row) => (
            <div key={row.visitId} className="grid grid-cols-1 gap-2 p-3 md:grid-cols-6">
              <div><span className="rounded-full bg-blue-100 px-2 py-1 text-xs text-blue-700">{row.token || "Token pending"}</span></div>
              <div>
                <p className="font-semibold">{row.patientName}</p>
                <p className="text-xs text-clinic-muted">{row.patientId}</p>
              </div>
              <p className="truncate text-sm">{row.mobile || "-"}</p>
              <p className="text-sm text-clinic-muted">{row.questionCount} Q&A</p>
              <p className="text-sm text-clinic-muted">{row.intakeStatus}</p>
              <button onClick={() => navigate(`/careprep/${row.visitId}`)} className="rounded-lg border border-clinic-border bg-white px-3 py-1 text-sm">Open session</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
