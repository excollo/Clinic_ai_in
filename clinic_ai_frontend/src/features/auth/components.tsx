import { type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ClinicLogo } from "@/components/ClinicLogo";
import { formatIndianMobileForInput, normalizeIndianMobile } from "@/lib/format";
import { sendOtp, verifyOtp } from "@/lib/mocks/auth";

export function MobileInput({ value, onChange, autoFocus = false }: { value: string; onChange: (digits: string) => void; autoFocus?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center rounded-xl border border-clinic-border bg-white px-3">
      <span className="text-sm text-clinic-muted">+91</span>
      <input
        autoFocus={autoFocus}
        value={formatIndianMobileForInput(value)}
        onChange={(e) => onChange(normalizeIndianMobile(e.target.value))}
        className="focus-ring w-full rounded-xl border-none px-2 py-3 text-sm"
        inputMode="numeric"
        aria-label={t("auth.mobileAriaLabel")}
      />
    </div>
  );
}

export function OtpInput({ mobile, requestId, onVerified }: { mobile: string; requestId: string; onVerified: (otp: string) => void }) {
  const { t } = useTranslation();
  const [digits, setDigits] = useState(Array(6).fill(""));
  const [timer, setTimer] = useState(30);
  const [attempts, setAttempts] = useState(0);
  const [locked, setLocked] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const id = window.setInterval(() => setTimer((prev) => Math.max(prev - 1, 0)), 1000);
    return () => window.clearInterval(id);
  }, []);

  const otp = digits.join("");
  const handleVerify = async () => {
    if (locked) return;
    try {
      await verifyOtp({ mobile, otp, request_id: requestId });
      toast.success(t("auth.otpSent"));
      onVerified(otp);
    } catch {
      const nextAttempts = attempts + 1;
      setAttempts(nextAttempts);
      if (nextAttempts >= 3) {
        setLocked(true);
        toast.error(t("auth.otpLocked"));
      } else {
        toast.error(t("auth.otpInvalid"));
      }
    }
  };

  const handleResend = async () => {
    if (timer > 0) return;
    await sendOtp(mobile);
    setDigits(Array(6).fill(""));
    setAttempts(0);
    setLocked(false);
    setTimer(30);
  };

  return (
    <div className="space-y-4">
      {import.meta.env.DEV && <p className="rounded-lg bg-amber-100 px-3 py-2 text-xs text-amber-700">{t("auth.otpDevBanner")}</p>}
      <div className="flex gap-2">
        {digits.map((digit, idx) => (
          <input
            key={idx}
            value={digit}
            maxLength={1}
            onChange={(e) => {
              const next = [...digits];
              next[idx] = e.target.value.replace(/\D/g, "");
              setDigits(next);
              if (e.target.value && idx < 5) {
                (document.getElementById(`otp-${idx + 1}`) as HTMLInputElement | null)?.focus();
              }
            }}
            id={`otp-${idx}`}
            className="focus-ring h-12 w-12 rounded-xl border border-clinic-border text-center text-lg"
            inputMode="numeric"
          />
        ))}
      </div>
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => void handleResend()} disabled={timer > 0} className="text-xs text-clinic-primary disabled:opacity-50">
          {t("auth.resendOtp")} {timer > 0 ? `(${timer}s)` : ""}
        </button>
        <div className="flex gap-2">
          <button type="button" onClick={() => navigate(-1)} className="rounded-xl border border-clinic-border px-3 py-2 text-sm">{t("common.back")}</button>
          <button type="button" onClick={() => void handleVerify()} className="rounded-xl bg-clinic-primary px-3 py-2 text-sm text-white" disabled={otp.length !== 6 || locked}>
            {t("common.verify")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-clinic-surface px-4">
      <div className="clinic-card w-full max-w-xl p-8">
        <div className="mb-6 flex items-center justify-between">
          <ClinicLogo />
          <p className="text-sm font-semibold">{title}</p>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, required = false, error, children }: { label: string; required?: boolean; error?: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-caption text-clinic-muted">{label} {required && <span className="text-red-600">*</span>}</label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
