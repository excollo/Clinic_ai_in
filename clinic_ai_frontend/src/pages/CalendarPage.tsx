import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RegisterPatientModal } from "@/components/RegisterPatientModal";
import apiClient from "@/lib/apiClient";
import { useAuthStore } from "@/lib/authStore";

type ViewMode = "day" | "week" | "month";
type CalendarAppointment = {
  id: string;
  visitId: string;
  patientName: string;
  visitType: "scheduled" | "follow-up" | "chronic care";
  start: string;
  end: string;
};

export default function CalendarPage() {
  const { t } = useTranslation();
  const [view, setView] = useState<ViewMode>("week");
  const [selectedDay, setSelectedDay] = useState(new Date());
  const [slotModalOpen, setSlotModalOpen] = useState(false);
  const [prefill, setPrefill] = useState<{ date?: string; time?: string }>({});
  const [popoverId, setPopoverId] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const doctorId = useAuthStore((s) => s.doctorId);
  const appointmentsQuery = useQuery({
    queryKey: ["calendar-appointments", doctorId],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await apiClient.get(`/visits/provider/${doctorId}/upcoming`);
      const rows = (response.data?.appointments ?? []) as Array<{
        appointment_id?: string;
        visit_id?: string;
        patient_name?: string;
        appointment_type?: string;
        scheduled_start?: string;
        status?: string;
      }>;

      const mapped: CalendarAppointment[] = rows
        .filter((row) => Boolean(row.scheduled_start) && Boolean(row.visit_id || row.appointment_id))
        .map((row) => {
          const start = new Date(row.scheduled_start as string);
          const end = new Date(start);
          end.setMinutes(end.getMinutes() + 20);
          const rawType = String(row.appointment_type ?? "").toLowerCase();
          const visitType: CalendarAppointment["visitType"] =
            rawType === "follow-up" || rawType === "follow up"
              ? "follow-up"
              : rawType === "chronic care"
                ? "chronic care"
                : "scheduled";
          const resolvedVisitId = String(row.visit_id || row.appointment_id);
          return {
            id: String(row.appointment_id || resolvedVisitId),
            visitId: resolvedVisitId,
            patientName: row.patient_name || "Unknown Patient",
            visitType,
            start: start.toISOString(),
            end: end.toISOString(),
          };
        });
      return mapped;
    },
  });
  const appointments = appointmentsQuery.data ?? [];
  const grouped = useMemo(() => {
    const map = new Map<string, CalendarAppointment[]>();
    appointments.forEach((item) => {
      const key = item.start.slice(0, 10);
      map.set(key, [...(map.get(key) ?? []), item]);
    });
    return map;
  }, [appointments]);

  const chipColor = (type: string) => (type === "follow-up" ? "bg-green-100 text-green-700" : type === "chronic care" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-h2">{t("calendar.title")}</h2>
          <p className="text-sm text-clinic-muted">{t("calendar.subtitle")}</p>
        </div>
        <button
          onClick={() => {
            const d = new Date();
            setPrefill({ date: d.toISOString().slice(0, 10), time: `${String(d.getHours()).padStart(2, "0")}:00` });
            setSlotModalOpen(true);
          }}
          className="rounded-xl bg-clinic-primary px-4 py-2 text-white"
        >
          Add Appointment
        </button>
      </div>
      <div className="flex gap-2">
        {(["day", "week", "month"] as const).map((v) => (
          <button key={v} onClick={() => setView(v)} className={`rounded-lg px-3 py-1 text-sm ${view === v ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>{t(`calendar.${v}`)}</button>
        ))}
      </div>
      {appointmentsQuery.isLoading && <p className="text-sm text-clinic-muted">Loading appointments...</p>}
      {appointmentsQuery.isError && <p className="text-sm text-red-600">Failed to load appointments from server.</p>}

      {view === "week" && (
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: 7 }).map((_, i) => {
            const d = new Date();
            d.setDate(d.getDate() - d.getDay() + i);
            const key = d.toISOString().slice(0, 10);
            const items = grouped.get(key) ?? [];
            const isToday = new Date().toISOString().slice(0, 10) === key;
            return (
              <div key={key} className={`min-h-56 rounded-xl border p-2 ${isToday ? "bg-indigo-50 border-indigo-200" : "border-clinic-border bg-white"}`}>
                <p className="mb-2 text-xs font-semibold">{d.toDateString().slice(0, 10)}</p>
                <div className="space-y-1">
                  {items.map((a) => (
                    <div key={a.id} className="relative">
                    <button key={a.id} onClick={() => setPopoverId((prev) => (prev === a.id ? null : a.id))} className={`block w-full rounded px-2 py-1 text-left text-xs ${chipColor(a.visitType)}`}>
                      {a.patientName} · {new Date(a.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </button>
                    {popoverId === a.id && (
                      <div className="absolute z-10 mt-1 w-56 rounded-xl border border-clinic-border bg-white p-2 text-xs shadow">
                        <p className="font-semibold">{a.patientName}</p>
                        <p className="text-clinic-muted">{new Date(a.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · {a.visitType}</p>
                        <div className="mt-2 grid gap-1">
                          <button className="rounded border px-2 py-1 text-left" onClick={() => navigate(`/visits/${a.visitId}`)}>{t("calendar.startVisit")}</button>
                          <button
                            className="rounded border px-2 py-1 text-left"
                            onClick={() => {
                              setPrefill({ date: a.start.slice(0, 10), time: new Date(a.start).toTimeString().slice(0, 5) });
                              setSlotModalOpen(true);
                            }}
                          >
                            {t("calendar.reschedule")}
                          </button>
                          <button className="rounded border px-2 py-1 text-left text-red-700" onClick={() => window.confirm(t("calendar.cancelConfirm"))}>{t("calendar.cancel")}</button>
                          <button className="rounded border px-2 py-1 text-left" onClick={() => alert(t("calendar.reminderSent"))}>{t("calendar.sendReminder")}</button>
                        </div>
                      </div>
                    )}
                    </div>
                  ))}
                  <button
                    onClick={() => {
                      setPrefill({ date: key, time: "09:00" });
                      setSlotModalOpen(true);
                    }}
                    className="w-full rounded border border-dashed border-clinic-border px-2 py-1 text-left text-xs text-clinic-muted"
                  >
                    + Add at this day
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {view === "day" && (
        <div className="clinic-card divide-y">
          {(grouped.get(selectedDay.toISOString().slice(0, 10)) ?? []).map((a) => (
            <button key={a.id} onClick={() => navigate(`/visits/${a.visitId}`)} className="flex w-full items-center justify-between p-3 text-left">
              <span>{a.patientName}</span>
              <span className={`rounded-full px-2 py-1 text-xs ${chipColor(a.visitType)}`}>{a.visitType}</span>
            </button>
          ))}
        </div>
      )}

      {view === "month" && (
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: 35 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl border border-clinic-border bg-white p-2 text-xs">
              {i + 1}
              <div className="mt-2 flex gap-1">{i % 3 === 0 && <span className="h-2 w-2 rounded-full bg-blue-400" />}{i % 4 === 0 && <span className="h-2 w-2 rounded-full bg-green-400" />}</div>
            </div>
          ))}
        </div>
      )}
      <RegisterPatientModal
        open={slotModalOpen}
        onClose={() => setSlotModalOpen(false)}
        onRegistered={() => {
          void queryClient.invalidateQueries({ queryKey: ["calendar-appointments", doctorId] });
        }}
        initialWorkflow="scheduled"
        initialSchedule={prefill}
      />
    </div>
  );
}
