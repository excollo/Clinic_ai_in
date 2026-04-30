import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import apiClient from "@/lib/apiClient";

export default function AuditLogTab() {
  const { t } = useTranslation();
  const doctorId = localStorage.getItem("clinic_doctor_id") || "";
  const [action, setAction] = useState("");
  const query = useQuery({
    queryKey: ["audit-log", doctorId, action],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await apiClient.get("/audit-log", { params: { doctor_id: doctorId, action: action || undefined, limit: 100, offset: 0 } });
      return (response.data?.entries ?? []) as Array<Record<string, string>>;
    },
  });
  const rows = query.data ?? [];
  return (
    <div className="overflow-x-auto">
      <div className="mb-3 flex items-center gap-2">
        <input value={action} onChange={(e) => setAction(e.target.value)} className="rounded border px-2 py-1 text-sm" placeholder="Filter by action" />
        <button
          className="rounded border px-2 py-1 text-sm"
          onClick={async () => {
            const response = await apiClient.get("/audit-log/export", { params: { doctor_id: doctorId, format: "csv" } });
            const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "audit-log.csv";
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          Export CSV
        </button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left"><th>{t("settings.auditDate")}</th><th>{t("settings.auditAction")}</th><th>{t("settings.auditPatient")}</th><th>{t("settings.auditUser")}</th><th>{t("settings.auditIp")}</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.entry_id)} className="border-t">
              <td>{new Date(String(r.timestamp || "")).toLocaleString()}</td>
              <td>{String(r.action || "")}</td>
              <td>{String(r.patient_id || "-")}</td>
              <td>{String(r.doctor_id || "-")}</td>
              <td>{String(r.ip_address || "-")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!query.isLoading && rows.length === 0 && (
        <div className="mt-4 rounded border border-dashed p-4 text-sm text-clinic-muted">No audit entries yet</div>
      )}
      {query.isError && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-700">Failed to load audit log.</div>
      )}
    </div>
  );
}
