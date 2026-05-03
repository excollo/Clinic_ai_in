/** Convert HH:mm (24h) ↔ 12h clock for UI. Backend/signup payloads stay HH:mm. */

export type Period = "AM" | "PM";

export type TimeParts12 = {
  hour12: number;
  minute: number;
  period: Period;
};

/** Parse HH:mm (24-hour) string into display parts; invalid empty → optional default or current time */
export function parseTime24To12Parts(time24: string | undefined, defaultFrom?: () => TimeParts12): TimeParts12 {
  const trimmed = (time24 || "").trim();
  const fallback = (): TimeParts12 => {
    if (defaultFrom) return defaultFrom();
    const d = new Date();
    const h = d.getHours();
    return { hour12: h % 12 || 12, minute: d.getMinutes(), period: h >= 12 ? "PM" : "AM" };
  };

  const match = /^(\d{1,2}):(\d{2})$/.exec(trimmed);
  if (!match) {
    return fallback();
  }
  const h24 = Math.min(23, Math.max(0, parseInt(match[1], 10)));
  let minute = parseInt(match[2], 10);
  if (!Number.isFinite(minute) || minute < 0 || minute > 59) {
    return fallback();
  }

  const period: Period = h24 >= 12 ? "PM" : "AM";
  const hour12 = h24 % 12 || 12;
  minute = Math.min(59, Math.max(0, minute));
  return { hour12, minute, period };
}

export function toTime24(hour12: number, minute: number, period: Period): string {
  const h = Math.min(12, Math.max(1, hour12));
  const m = Math.min(59, Math.max(0, minute));

  let h24: number;
  if (period === "AM") {
    h24 = h === 12 ? 0 : h;
  } else {
    h24 = h === 12 ? 12 : h + 12;
  }
  return `${String(h24).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
