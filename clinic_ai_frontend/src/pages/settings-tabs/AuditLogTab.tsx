import { useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useTranslation } from "react-i18next";
import { auditEntries } from "@/lib/mocks/settings";

export default function AuditLogTab() {
  const { t } = useTranslation();
  const parentRef = useRef<HTMLDivElement | null>(null);
  const rows = useMemo(() => Array.from({ length: 120 }).map((_, i) => ({ ...auditEntries[i % auditEntries.length], id: `${auditEntries[i % auditEntries.length].id}_${i}` })), []);
  const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => parentRef.current, estimateSize: () => 40, overscan: 8 });
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left"><th>{t("settings.auditDate")}</th><th>{t("settings.auditAction")}</th><th>{t("settings.auditPatient")}</th><th>{t("settings.auditUser")}</th><th>{t("settings.auditIp")}</th></tr>
        </thead>
      </table>
      <div ref={parentRef} className="max-h-[50vh] overflow-auto">
        <table className="w-full text-sm">
          <tbody style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative", display: "block" }}>
            {virtualizer.getVirtualItems().map((item) => {
              const r = rows[item.index];
              return (
                <tr key={r.id} className="border-t" style={{ position: "absolute", transform: `translateY(${item.start}px)`, display: "table", width: "100%", tableLayout: "fixed" }}>
                  <td>{new Date(r.date).toLocaleString()}</td><td>{r.actionType}</td><td>{r.patient}</td><td>{r.user}</td><td>{r.ip}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
