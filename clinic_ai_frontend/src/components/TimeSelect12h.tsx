import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Period } from "@/lib/time12h";
import { parseTime24To12Parts, toTime24 } from "@/lib/time12h";

const HOURS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;
const MINUTES = Array.from({ length: 60 }, (_, i) => i);

export type TimeSelect12hProps = {
  /** Value in HH:mm (24-hour), e.g. "14:30" */
  value: string;
  onChange: (next24h: string) => void;
  disabled?: boolean;
  /** Used when value is blank/invalid (display only until user changes) */
  displayFallback?: string;
  /** Additional class on the wrapping flex row */
  className?: string;
  /** id for accessibility (links to labels) */
  id?: string;
};

export default function TimeSelect12h({
  value,
  onChange,
  disabled,
  displayFallback = "09:00",
  className,
  id,
}: TimeSelect12hProps) {
  const { t } = useTranslation();
  const selectClass =
    "focus-ring min-w-0 flex-1 rounded-xl border border-clinic-border bg-white px-2 py-2 text-sm md:px-3 md:py-3";

  const parts = useMemo(
    () => parseTime24To12Parts(value, () => parseTime24To12Parts(displayFallback)),
    [value, displayFallback],
  );

  const commit = (hour12: number, minute: number, period: Period) => {
    onChange(toTime24(hour12, minute, period));
  };

  return (
    <div id={id} className={`flex flex-wrap items-stretch gap-2 ${className ?? ""}`}>
      <select
        className={selectClass}
        aria-label={t("time.hour")}
        disabled={disabled}
        value={parts.hour12}
        onChange={(e) => commit(Number(e.target.value), parts.minute, parts.period)}
      >
        {HOURS.map((h) => (
          <option key={h} value={h}>
            {h}
          </option>
        ))}
      </select>
      <select
        className={selectClass}
        aria-label={t("time.minute")}
        disabled={disabled}
        value={parts.minute}
        onChange={(e) => commit(parts.hour12, Number(e.target.value), parts.period)}
      >
        {MINUTES.map((m) => (
          <option key={m} value={m}>
            {String(m).padStart(2, "0")}
          </option>
        ))}
      </select>
      <select
        className={selectClass}
        aria-label={t("time.period")}
        disabled={disabled}
        value={parts.period}
        onChange={(e) => commit(parts.hour12, parts.minute, e.target.value as Period)}
      >
        <option value="AM">{t("time.am")}</option>
        <option value="PM">{t("time.pm")}</option>
      </select>
    </div>
  );
}
