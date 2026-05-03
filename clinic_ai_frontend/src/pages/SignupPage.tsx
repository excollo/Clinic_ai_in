import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthFlowStore } from "@/lib/authFlowStore";
import { isValidIndianMobile } from "@/lib/format";
import { sendOtp, signupDoctor } from "@/lib/mocks/auth";
import { AuthCard, Field, MobileInput, OtpInput } from "@/features/auth/components";
import TimeSelect12h from "@/components/TimeSelect12h";

export default function SignupPage() {
  const { t } = useTranslation();
  useDocumentTitle(`Sign up · ${t("common.brand")}`);
  const navigate = useNavigate();
  const { signup, updateSignup } = useAuthFlowStore();
  const resetSignup = useAuthFlowStore((s) => s.resetSignup);
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [otpRequestId, setOtpRequestId] = useState(signup.otpRequestId);
  const form = useForm({ mode: "onBlur", defaultValues: signup });

  const sendSignupOtp = async () => {
    const values = form.getValues();
    const mobile = (values.mobile || signup.mobile || "").trim();
    if (!isValidIndianMobile(mobile)) {
      toast.error(t("auth.mobileValidation"));
      return;
    }
    try {
      const res = await sendOtp(mobile);
      setOtpRequestId(res.request_id);
      updateSignup({
        fullName: values.fullName || signup.fullName,
        mobile,
        email: values.email || signup.email,
        regNo: values.regNo || signup.regNo,
        specialty: values.specialty || signup.specialty,
        password: values.password || signup.password,
        otpRequestId: res.request_id,
      });
      setStep(2);
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string | { detail?: string } } } })?.response?.data?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : typeof detail === "object" && detail?.detail
            ? detail.detail
            : t("common.error");
      toast.error(message);
    }
  };
  const finishSignup = async () => {
    const values = form.getValues();
    const draft = {
      ...signup,
      ...values,
    };
    try {
      if (draft.hasEveningShift && (!draft.eveningStart || !draft.eveningEnd)) {
        toast.error(t("auth.requiredField"));
        return;
      }
      const shifts = [
        { name: "morning", start: draft.opdStart, end: draft.opdEnd },
        ...(draft.hasEveningShift ? [{ name: "evening", start: draft.eveningStart, end: draft.eveningEnd }] : []),
      ];
      const response = await signupDoctor({
        name: draft.fullName,
        mobile: draft.mobile,
        email: draft.email || undefined,
        mci_number: draft.regNo,
        specialty: draft.specialty,
        password: draft.password,
        clinic_name: draft.clinicName,
        city: draft.city,
        pincode: draft.pincode,
        opd_hours: {
          start: draft.opdStart,
          end: draft.opdEnd,
          morning: { start: draft.opdStart, end: draft.opdEnd },
          evening: draft.hasEveningShift ? { start: draft.eveningStart, end: draft.eveningEnd } : undefined,
          shifts,
        },
        languages: draft.languages,
        token_prefix: draft.tokenPrefix || "OPD-",
        abdm_hfr_id: draft.hfrId || undefined,
        whatsapp_mode: draft.whatsappChoice,
      });
      if (response?.doctor_id) {
        sessionStorage.setItem(
          "clinic_signup_prefill",
          JSON.stringify({ mobile: draft.mobile, password: draft.password, doctorName: draft.fullName }),
        );
      }
      resetSignup();
      toast.success(t("auth.accountCreatedLogin"));
      navigate("/login", { state: { mobile: draft.mobile, password: draft.password, fromSignup: true } });
    } catch (error) {
      const status = (error as { response?: { status?: number; data?: { detail?: string } } })?.response?.status;
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "";
      if (status === 409) {
        toast.error(detail || "Account already exists. Please sign in.");
        navigate("/login", { state: { mobile: draft.mobile, fromSignup: true } });
        return;
      }
      toast.error(detail || t("common.error"));
    }
  };
  useEffect(() => {
    if (step === 5) {
      void import("@/pages/DashboardPage");
    }
  }, [step]);

  const hasEveningShift = Boolean(form.watch("hasEveningShift"));
  useEffect(() => {
    if (step !== 3) return;
    const ok = (s: unknown) => typeof s === "string" && /^\d{2}:\d{2}$/.test(s.trim());
    if (!ok(form.getValues("opdStart"))) form.setValue("opdStart", "09:00");
    if (!ok(form.getValues("opdEnd"))) form.setValue("opdEnd", "18:00");
  }, [step, form]);
  useEffect(() => {
    if (step !== 3 || !hasEveningShift) return;
    const ok = (s: unknown) => typeof s === "string" && /^\d{2}:\d{2}$/.test(s.trim());
    if (!ok(form.getValues("eveningStart"))) form.setValue("eveningStart", "17:00");
    if (!ok(form.getValues("eveningEnd"))) form.setValue("eveningEnd", "21:00");
  }, [step, hasEveningShift, form]);
  const stepLabels = [t("auth.doctorDetails"), t("auth.otpVerification"), t("auth.clinicSetup"), `${t("auth.abdmLinkage")} (${t("common.optional")})`, `${t("auth.whatsappSetup")} (${t("common.optional")})`];

  return (
    <AuthCard title={t("auth.createAccount")}>
      <div className="mb-4 grid grid-cols-5 gap-2">{stepLabels.map((label, idx) => <div key={label} className={`h-2 rounded-full ${idx + 1 <= step ? "bg-clinic-primary" : "bg-slate-200"}`} />)}</div>
      <p className="mb-3 text-sm text-clinic-muted">{stepLabels[step - 1]}</p>
      {step === 1 && (
        <form className="space-y-3" onSubmit={form.handleSubmit(() => void sendSignupOtp())}>
          <Field label={t("auth.fullName")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("fullName", { required: true })} /></Field>
          <Field label={t("auth.mobileNumber")} required>
            <input type="hidden" {...form.register("mobile", { required: true, validate: isValidIndianMobile })} />
            <MobileInput
              value={form.watch("mobile") || ""}
              onChange={(v) => {
                form.setValue("mobile", v, { shouldDirty: true, shouldValidate: true });
                updateSignup({ mobile: v });
              }}
            />
          </Field>
          <Field label={t("auth.emailOptional")}><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("email")} /></Field>
          <Field label={t("auth.registrationNumber")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("regNo", { required: true })} /></Field>
          <Field label={t("auth.specialty")} required><select className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("specialty", { required: true })}><option value="">{t("auth.specialtySelect")}</option><option>{t("auth.specialtyGeneralMedicine")}</option><option>{t("auth.specialtyPediatrics")}</option><option>{t("auth.specialtyCardiology")}</option><option>{t("auth.specialtyGynecology")}</option><option>{t("auth.specialtyDermatology")}</option><option>{t("auth.specialtyOrthopedics")}</option><option>{t("auth.specialtyEnt")}</option><option>{t("auth.specialtyPsychiatry")}</option><option>{t("auth.specialtyOther")}</option></select></Field>
          <Field label={t("auth.password")} required><input type="password" className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("password", { required: true })} /></Field>
          <div className="flex justify-end"><button className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("common.continue")}</button></div>
        </form>
      )}
      {step === 2 && <OtpInput mobile={signup.mobile} requestId={otpRequestId} onVerified={() => setStep(3)} />}
      {step === 3 && (
        <form className="space-y-3" onSubmit={form.handleSubmit(() => setStep(4))}>
          <Field label={t("auth.clinicName")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("clinicName", { required: true })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("auth.city")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("city", { required: true })} /></Field>
            <Field label={t("auth.pincode")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("pincode", { required: true })} /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("auth.opdStart")} required>
              <input type="hidden" {...form.register("opdStart", { required: true })} />
              <TimeSelect12h
                value={form.watch("opdStart") || "09:00"}
                displayFallback="09:00"
                onChange={(v) => form.setValue("opdStart", v, { shouldDirty: true, shouldValidate: true })}
              />
            </Field>
            <Field label={t("auth.opdEnd")} required>
              <input type="hidden" {...form.register("opdEnd", { required: true })} />
              <TimeSelect12h
                value={form.watch("opdEnd") || "18:00"}
                displayFallback="18:00"
                onChange={(v) => form.setValue("opdEnd", v, { shouldDirty: true, shouldValidate: true })}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 rounded-xl border border-clinic-border px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(form.watch("hasEveningShift"))}
              onChange={(e) => form.setValue("hasEveningShift", e.target.checked)}
            />
            {t("auth.secondShift")}
          </label>
          {form.watch("hasEveningShift") && (
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("auth.eveningStart")} required>
                <input type="hidden" {...form.register("eveningStart", { required: true })} />
                <TimeSelect12h
                  value={form.watch("eveningStart") || "17:00"}
                  displayFallback="17:00"
                  onChange={(v) => form.setValue("eveningStart", v, { shouldDirty: true, shouldValidate: true })}
                />
              </Field>
              <Field label={t("auth.eveningEnd")} required>
                <input type="hidden" {...form.register("eveningEnd", { required: true })} />
                <TimeSelect12h
                  value={form.watch("eveningEnd") || "21:00"}
                  displayFallback="21:00"
                  onChange={(v) => form.setValue("eveningEnd", v, { shouldDirty: true, shouldValidate: true })}
                />
              </Field>
            </div>
          )}
          <Field label={t("auth.tokenPrefix")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("tokenPrefix", { required: true })} /></Field>
          <div className="flex justify-between"><button type="button" className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(2)}>{t("common.back")}</button><button className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("common.continue")}</button></div>
        </form>
      )}
      {step === 4 && (
        <div className="space-y-3">
          <div className="rounded-xl bg-blue-50 p-3 text-sm text-blue-700">{t("auth.abdmInfo")}</div>
          <Field label={t("auth.hfrId")}><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" value={signup.hfrId} onChange={(e) => updateSignup({ hfrId: e.target.value })} /></Field>
          <p className="text-xs text-clinic-muted">{t("auth.abdmApplyHint")}</p>
          <div className="flex justify-between gap-2">
            <button type="button" className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(3)}>{t("common.back")}</button>
            <button type="button" className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(5)}>{t("auth.skipForNow")}</button>
            <button type="button" className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => setStep(5)}>{t("auth.link")}</button>
          </div>
        </div>
      )}
      {step === 5 && (
        <div className="space-y-3">
          <label className="block rounded-xl border border-clinic-border p-3"><input type="radio" name="wa" checked={signup.whatsappChoice === "platform_default"} onChange={() => updateSignup({ whatsappChoice: "platform_default" })} /> {t("auth.waPlatformDefault")}</label>
          <label className="block rounded-xl border border-clinic-border p-3"><input type="radio" name="wa" checked={signup.whatsappChoice === "own_number"} onChange={() => updateSignup({ whatsappChoice: "own_number" })} /> {t("auth.waOwnNumber")}</label>
          <div className="flex justify-between gap-2">
            <button type="button" className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(4)}>{t("common.back")}</button>
            <button type="button" className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => void finishSignup()}>{t("common.skip")}</button>
            <button type="button" className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => void finishSignup()}>{t("auth.finishSetup")}</button>
          </div>
        </div>
      )}
    </AuthCard>
  );
}
