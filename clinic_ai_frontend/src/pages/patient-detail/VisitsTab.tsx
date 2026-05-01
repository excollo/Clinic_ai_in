import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import type { PatientRecord } from "@/features/patients/hooks/usePatients";
import { formatClinicDate } from "@/lib/format";
import apiClient from "@/lib/apiClient";

type VisitListItem = {
  id?: string;
  visit_id?: string;
  status?: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export default function VisitsTab({ patient }: { patient: PatientRecord }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const visitsQuery = useQuery({
    queryKey: ["patient-visits", patient.patient_id],
    enabled: Boolean(patient.patient_id),
    queryFn: async () => {
      const response = await apiClient.get(`/api/visits/patient/${patient.patient_id}`);
      const rows = Array.isArray(response.data) ? (response.data as VisitListItem[]) : [];
      return rows.map((row) => ({
        id: String(row.visit_id || row.id || ""),
        date: new Date(String(row.created_at || row.updated_at || new Date().toISOString())),
        status: String(row.status || "open"),
      }));
    },
  });

  const visits = visitsQuery.data ?? [];
  return (
    <div className="space-y-2">
      {!visitsQuery.isLoading && visits.length === 0 && (
        <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-clinic-muted">
          No visits found for this patient.
        </div>
      )}
      {visits.map((v) => (
        <button key={v.id} onClick={() => navigate(`/visits/${v.id}`)} className="clinic-card w-full p-3 text-left">
          <p className="text-sm font-semibold">{formatClinicDate(v.date)}</p>
          <p className="text-xs text-clinic-muted">{v.status}</p>
        </button>
      ))}
    </div>
  );
}
