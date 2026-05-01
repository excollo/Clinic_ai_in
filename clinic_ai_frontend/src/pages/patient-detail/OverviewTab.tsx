import type { PatientRecord } from "@/features/patients/hooks/usePatients";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/apiClient";

export default function OverviewTab({ patient }: { patient: PatientRecord }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [banner, setBanner] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["consent-history", patient.id, open],
    enabled: open,
    queryFn: async () => {
      const response = await apiClient.get(`/consent/${patient.id}/history`);
      return (response.data ?? []) as Array<Record<string, string>>;
    },
  });
  return (
    <div className="space-y-3">
      {banner && <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">{banner}</div>}
      <div className="flex items-center gap-3">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-indigo-100 text-lg font-semibold text-indigo-700">{patient.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}</span>
        <div>
          <p className="text-lg font-semibold">{patient.name}</p>
          <p className="text-sm text-clinic-muted">{patient.age} · {patient.sex}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="clinic-card p-3">{t("patientDetail.totalVisits")}: {patient.visitCount}</div>
        <div className="clinic-card p-3">{t("patientDetail.lastConsentVersion")}: v1.2</div>
      </div>
      <button onClick={() => setOpen(true)} className="rounded-xl border border-clinic-border px-4 py-2 text-sm">Manage Consent</button>
      {open && (
        <div className="rounded-xl border border-clinic-border bg-white p-4">
          <p className="mb-2 text-sm font-semibold">Consent history</p>
          <div className="max-h-40 space-y-2 overflow-auto text-sm">
            {(query.data ?? []).map((item, idx) => (
              <div key={idx} className="rounded border p-2">
                <p>{String(item.status)} · {String(item.timestamp || "")}</p>
                {item.withdrawal_reason && <p className="text-clinic-muted">{String(item.withdrawal_reason)}</p>}
              </div>
            ))}
            {!query.isLoading && (query.data ?? []).length === 0 && <p className="text-clinic-muted">No consent entries yet.</p>}
          </div>
          <div className="mt-3 flex gap-2">
            <input value={reason} onChange={(e) => setReason(e.target.value)} className="flex-1 rounded border px-2 py-1 text-sm" placeholder="Withdrawal reason" />
            <button
              onClick={async () => {
                await apiClient.post("/consent/withdraw", {
                  patient_id: patient.id,
                  withdrawal_reason: reason || undefined,
                  initiated_by: "doctor",
                });
                setBanner(`Consent withdrawn for this patient on ${new Date().toLocaleString()} - visits cannot be started.`);
                setOpen(false);
              }}
              className="rounded bg-red-600 px-3 py-1 text-sm text-white"
            >
              Withdraw consent
            </button>
            <button onClick={() => setOpen(false)} className="rounded border px-3 py-1 text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
