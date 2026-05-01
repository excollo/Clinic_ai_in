import { useMemo, useState } from "react";
import { useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronRight, FlaskConical, MessageCircleWarning, RefreshCw } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/lib/authStore";
import apiClient from "@/lib/apiClient";

type NotificationItem = {
  notification_id?: string;
  id?: string;
  type?: string;
  title?: string;
  message?: string;
  target?: string;
  created_at?: string;
  createdAt?: string;
};

export default function NotificationsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const doctorId = useAuthStore((s) => s.doctorId ?? "");
  const [filter, setFilter] = useState("all");
  const listRef = useRef<HTMLDivElement | null>(null);
  const query = useQuery({
    queryKey: ["notifications", doctorId, filter],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await apiClient.get("/notifications", {
        params: { doctor_id: doctorId, limit: 200, offset: 0, filter },
      });
      return {
        notifications: (response.data?.notifications ?? []) as NotificationItem[],
        unreadCount: Number(response.data?.unread_count ?? 0),
      };
    },
  });
  const rows = useMemo(
    () =>
      (query.data?.notifications ?? []).map((n, idx) => ({
        id: String(n.notification_id || n.id || `notif_${idx}`),
        type: String(n.type || "follow_up_due"),
        title: String(n.title || "Notification"),
        description: String(n.message || ""),
        target: String(n.target || "/dashboard"),
        createdAt: String(n.created_at || n.createdAt || new Date().toISOString()),
      })),
    [query.data?.notifications],
  );
  const virtualizer = useVirtualizer({ count: rows.length, getScrollElement: () => listRef.current, estimateSize: () => 72, overscan: 10 });
  const unread = Number(query.data?.unreadCount ?? 0);
  const icon = (type: string) => (type === "lab_ready" ? <FlaskConical className="h-4 w-4" /> : type === "follow_up_due" ? <RefreshCw className="h-4 w-4" /> : <MessageCircleWarning className="h-4 w-4" />);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-h2">{t("notifications.title")} <span className="ml-2 rounded-full bg-indigo-100 px-2 py-1 text-xs text-indigo-700">{unread}</span></h2>
        <button
          onClick={async () => {
            if (!doctorId) return;
            await apiClient.patch("/notifications/mark-all-read", { doctor_id: doctorId });
            await queryClient.invalidateQueries({ queryKey: ["notifications"] });
          }}
          className="rounded-xl border border-clinic-border bg-white px-3 py-2 text-sm"
        >
          {t("notifications.markAllRead")}
        </button>
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
        {!query.isLoading && rows.length === 0 && (
          <div className="p-6 text-sm text-clinic-muted">No notifications available.</div>
        )}
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
