import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/apiClient";
import { useAuthStore } from "@/lib/authStore";
import { toast } from "sonner";

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
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [importedRows, setImportedRows] = useState<CalendarAppointment[]>([]);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const doctorId = useAuthStore((s) => s.doctorId);
  const csvInputRef = useRef<HTMLInputElement | null>(null);
  const appointmentsQuery = useQuery({
    queryKey: ["calendar-appointments", doctorId],
    enabled: Boolean(doctorId),
    queryFn: async () => {
      const response = await apiClient.get(`/api/visits/provider/${doctorId}/upcoming`);
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
  const appointments = useMemo(
    () => [...(appointmentsQuery.data ?? []), ...importedRows],
    [appointmentsQuery.data, importedRows],
  );
  const grouped = useMemo(() => {
    const map = new Map<string, CalendarAppointment[]>();
    appointments.forEach((item) => {
      const key = item.start.slice(0, 10);
      map.set(key, [...(map.get(key) ?? []), item]);
    });
    return map;
  }, [appointments]);

  const monthDays = useMemo(() => {
    const firstDay = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1);
    const lastDay = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0);
    const leading = firstDay.getDay();
    const total = lastDay.getDate();
    const days: Array<Date | null> = [];
    for (let i = 0; i < leading; i += 1) days.push(null);
    for (let d = 1; d <= total; d += 1) {
      days.push(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), d));
    }
    while (days.length % 7 !== 0) days.push(null);
    return days;
  }, [calendarMonth]);

  const upcoming = useMemo(
    () =>
      [...appointments]
        .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
        .filter((a) => new Date(a.start).getTime() >= Date.now())
        .slice(0, 8),
    [appointments],
  );

  const parseCsvDateTime = (dateRaw: string, timeRaw: string) => {
    const date = (dateRaw || "").trim();
    const time = (timeRaw || "").trim();
    if (!date) return null;
    const normalizedDate = date.includes("/") ? date.split("/").reverse().join("-") : date;
    const normalizedTime = time || "09:00";
    const parsed = new Date(`${normalizedDate}T${normalizedTime}:00`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const handleImportCsv = async (file: File) => {
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((line) => line.trim());
    if (lines.length < 2) {
      toast.error("CSV is empty.");
      return;
    }
    const headers = lines[0].split(",").map((v) => v.trim().toLowerCase());
    const idxName = headers.findIndex((h) => h === "patient_name" || h === "name");
    const idxDate = headers.findIndex((h) => h === "date" || h === "scheduled_date");
    const idxTime = headers.findIndex((h) => h === "time" || h === "scheduled_time");
    if (idxName < 0 || idxDate < 0) {
      toast.error("CSV must include patient_name/name and date.");
      return;
    }

    const imported: CalendarAppointment[] = [];
    for (let i = 1; i < lines.length; i += 1) {
      const cols = lines[i].split(",").map((v) => v.trim());
      const patientName = cols[idxName] || "";
      const parsedStart = parseCsvDateTime(cols[idxDate] || "", idxTime >= 0 ? cols[idxTime] || "" : "");
      if (!patientName || !parsedStart) continue;
      const end = new Date(parsedStart);
      end.setMinutes(end.getMinutes() + 20);
      imported.push({
        id: `csv_${i}_${parsedStart.getTime()}`,
        visitId: "",
        patientName,
        visitType: "scheduled",
        start: parsedStart.toISOString(),
        end: end.toISOString(),
      });
    }
    setImportedRows(imported);
    toast.success(`Imported ${imported.length} appointments from CSV.`);
  };

  const chipColor = (type: string) => (type === "follow-up" ? "bg-green-100 text-green-700" : type === "chronic care" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700");

  useEffect(() => {
    if (searchParams.get("new") !== "1") return;
    const d = new Date();
    navigate("/register-patient", {
      state: {
        initialWorkflow: "scheduled",
        initialSchedule: {
          date: d.toISOString().slice(0, 10),
          time: `${String(d.getHours()).padStart(2, "0")}:00`,
        },
      },
      replace: true,
    });
    const next = new URLSearchParams(searchParams);
    next.delete("new");
    setSearchParams(next, { replace: true });
  }, [navigate, searchParams, setSearchParams]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-h2">{t("calendar.title")}</h2>
          <p className="text-sm text-clinic-muted">{t("calendar.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => csvInputRef.current?.click()}
            className="rounded-xl border border-clinic-border bg-white px-4 py-2 text-sm"
          >
            Import CSV
          </button>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                void handleImportCsv(file);
                e.currentTarget.value = "";
              }
            }}
          />
          <button
            onClick={() => {
              const d = new Date();
              navigate("/register-patient", {
                state: {
                  initialWorkflow: "scheduled",
                  initialSchedule: {
                    date: d.toISOString().slice(0, 10),
                    time: `${String(d.getHours()).padStart(2, "0")}:00`,
                  },
                },
              });
            }}
            className="rounded-xl bg-clinic-primary px-4 py-2 text-white"
          >
            New Appointment
          </button>
        </div>
      </div>
      {appointmentsQuery.isLoading && <p className="text-sm text-clinic-muted">Loading appointments...</p>}
      {appointmentsQuery.isError && <p className="text-sm text-red-600">Failed to load appointments from server.</p>}

      <div className="rounded-2xl border border-clinic-border bg-white p-4">
        <div className="mb-4 flex items-center justify-between">
          <button
            className="rounded-lg border border-clinic-border px-3 py-1 text-sm"
            onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1))}
          >
            {"<"}
          </button>
          <p className="text-xl font-semibold">
            {calendarMonth.toLocaleString(undefined, { month: "long", year: "numeric" })}
          </p>
          <button
            className="rounded-lg border border-clinic-border px-3 py-1 text-sm"
            onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))}
          >
            {">"}
          </button>
        </div>
        <div className="mb-2 grid grid-cols-7 gap-2 text-center text-xs font-semibold text-clinic-muted">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
            <div key={day}>{day}</div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-2">
          {monthDays.map((date, idx) => {
            if (!date) return <div key={`blank_${idx}`} className="min-h-28 rounded-xl bg-slate-50/60" />;
            const key = date.toISOString().slice(0, 10);
            const items = grouped.get(key) ?? [];
            const isToday = new Date().toISOString().slice(0, 10) === key;
            return (
              <div key={key} className={`min-h-28 rounded-xl border p-2 ${isToday ? "border-indigo-300 bg-indigo-50/40" : "border-clinic-border"}`}>
                <p className="text-xs font-semibold">{date.getDate()}</p>
                <div className="mt-1 space-y-1">
                  {items.slice(0, 3).map((a) => (
                    <button
                      key={a.id}
                      onClick={() => (a.visitId ? navigate(`/visits/${a.visitId}`) : undefined)}
                      className={`block w-full rounded px-2 py-1 text-left text-[11px] ${chipColor(a.visitType)}`}
                    >
                      {new Date(a.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} {a.patientName}
                    </button>
                  ))}
                  {items.length > 3 && <p className="text-[11px] text-clinic-muted">+{items.length - 3} more</p>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-2xl border border-clinic-border bg-white p-4">
        <p className="mb-2 text-lg font-semibold">Upcoming Appointments</p>
        <div className="space-y-2">
          {upcoming.map((a) => (
            <div key={a.id} className="flex items-center justify-between rounded-xl border border-clinic-border p-3">
              <div>
                <p className="font-semibold">{a.patientName}</p>
                <p className="text-sm text-clinic-muted">
                  {new Date(a.start).toLocaleDateString()} · {new Date(a.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · {a.visitType}
                </p>
              </div>
              <button
                disabled={!a.visitId}
                onClick={() => a.visitId && navigate(`/visits/${a.visitId}`)}
                className="rounded-xl border border-clinic-border bg-white px-3 py-2 text-sm disabled:opacity-40"
              >
                Open Visit
              </button>
            </div>
          ))}
          {!appointmentsQuery.isLoading && upcoming.length === 0 && (
            <div className="rounded-xl border border-dashed border-clinic-border p-4 text-sm text-clinic-muted">
              No upcoming appointments.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
