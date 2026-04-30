import { useMemo, useState } from "react";
import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronRight, FlaskConical, MessageCircleWarning, RefreshCw } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { mockNotifications } from "@/lib/mocks/notifications";

export default function NotificationsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [filter, setFilter] = useState("all");
  const [readAll, setReadAll] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);
  const rows = useMemo(() => {
    const base = Array.from({ length: 120 }).map((_, i) => ({ ...mockNotifications[i % mockNotifications.length], id: `${mockNotifications[i % mockNotifications.length].id}_${i}` }));
    return base.filter((n) => filter === "all" || n.type === filter);
  }, [filter]);
  const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => listRef.current, estimateSize: () => 72, overscan: 10 });
  const unread = readAll ? 0 : rows.length;
  const icon = (type: string) => (type === "lab_ready" ? <FlaskConical className="h-4 w-4" /> : type === "follow_up_due" ? <RefreshCw className="h-4 w-4" /> : <MessageCircleWarning className="h-4 w-4" />);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-h2">{t("notifications.title")} <span className="ml-2 rounded-full bg-indigo-100 px-2 py-1 text-xs text-indigo-700">{unread}</span></h2>
        <button onClick={() => setReadAll(true)} className="rounded-xl border border-clinic-border bg-white px-3 py-2 text-sm">{t("notifications.markAllRead")}</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {[
          ["all", t("notifications.filterAll")],
          ["lab_ready", t("notifications.filterLabReady")],
          ["follow_up_due", t("notifications.filterFollowUp")],
          ["whatsapp_failed", t("notifications.filterWhatsAppFailed")],
          ["consent_pending_sync", t("notifications.filterConsentPending")],
          ["appointment_booked", t("notifications.filterAppointmentBooked")],
        ].map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)} className={`rounded-full px-3 py-1 text-xs ${filter === k ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>{l}</button>
        ))}
      </div>
      <div ref={listRef} className="clinic-card max-h-[70vh] overflow-auto">
        <div className="relative" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((item) => {
          const n = rows[item.index];
          return (
          <button key={n.id} style={{ transform: `translateY(${item.start}px)` }} onClick={() => navigate(n.target)} className="absolute left-0 top-0 flex w-full items-center justify-between gap-3 border-b border-clinic-border p-3 text-left">
            <div className="flex items-start gap-3">
              <span className="mt-1">{icon(n.type)}</span>
              <div>
                <p className="font-semibold">{n.title}</p>
                <p className="text-sm text-clinic-muted">{n.description}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-clinic-muted">
              <span>{formatDistanceToNow(new Date(n.createdAt), { addSuffix: true })}</span>
              <ChevronRight className="h-4 w-4" />
            </div>
          </button>
          );
        })}
        </div>
      </div>
    </div>
  );
}
