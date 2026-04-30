import { format, formatDistanceToNow, isYesterday } from "date-fns";
import { hi } from "date-fns/locale";

export function normalizeIndianMobile(input: string): string {
  return input.replace(/\D/g, "").slice(0, 10);
}

export function formatIndianMobileForInput(input: string): string {
  const digits = normalizeIndianMobile(input);
  if (digits.length <= 5) return digits;
  return `${digits.slice(0, 5)} ${digits.slice(5)}`;
}

export function isValidIndianMobile(input: string): boolean {
  return /^[6-9]\d{9}$/.test(normalizeIndianMobile(input));
}

export function formatClinicDate(date: Date, language: "en" | "hi" = "en"): string {
  return format(date, "dd MMM yyyy", { locale: language === "hi" ? hi : undefined });
}

export function formatClinicTime(date: Date): string {
  return format(date, "h:mm a");
}

export function formatRelativeClinicTime(date: Date): string {
  if (isYesterday(date)) return "yesterday";
  return formatDistanceToNow(date, { addSuffix: true });
}

export function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(value);
}
