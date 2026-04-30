import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/lib/authStore";
import { useAuthFlowStore } from "@/lib/authFlowStore";
import { sendOtp, signupDoctor } from "@/lib/mocks/auth";
import { AuthCard, Field, MobileInput, OtpInput } from "@/features/auth/components";

export default function SignupPage() {
  const { t } = useTranslation();
  useDocumentTitle(`Sign up · ${t("common.brand")}`);
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const { signup, updateSignup } = useAuthFlowStore();
  const resetSignup = useAuthFlowStore((s) => s.resetSignup);
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [otpRequestId, setOtpRequestId] = useState(signup.otpRequestId);
  const form = useForm({ mode: "onBlur", defaultValues: signup });
  const values = form.watch();
  useEffect(() => { updateSignup(values); }, [values, updateSignup]);

  const sendSignupOtp = async () => {
    const res = await sendOtp(signup.mobile);
    setOtpRequestId(res.request_id);
    updateSignup({ otpRequestId: res.request_id });
    setStep(2);
  };
  const finishSignup = async () => {
    const response = await signupDoctor({
      name: signup.fullName,
      mobile: signup.mobile,
      email: signup.email || undefined,
      mci_number: signup.regNo,
      specialty: signup.specialty,
      password: signup.password,
      clinic_name: signup.clinicName,
      city: signup.city,
      pincode: signup.pincode,
      opd_hours: { start: signup.opdStart, end: signup.opdEnd },
      languages: signup.languages,
      token_prefix: signup.tokenPrefix || "OPD-",
      abdm_hfr_id: signup.hfrId || undefined,
      whatsapp_mode: signup.whatsappChoice,
    });
    if (response?.token && response?.doctor_id) {
      setSession({
        apiKey: response.token,
        doctorId: response.doctor_id,
        doctorName: signup.fullName,
        mobile: signup.mobile,
      });
    }
    resetSignup();
    navigate("/welcome-tour");
  };
  useEffect(() => {
    if (step === 5) {
      void import("@/pages/DashboardPage");
    }
  }, [step]);
  const stepLabels = [t("auth.doctorDetails"), t("auth.otpVerification"), t("auth.clinicSetup"), `${t("auth.abdmLinkage")} (${t("common.optional")})`, `${t("auth.whatsappSetup")} (${t("common.optional")})`];

  return (
    <AuthCard title={t("auth.createAccount")}>
      <div className="mb-4 grid grid-cols-5 gap-2">{stepLabels.map((label, idx) => <div key={label} className={`h-2 rounded-full ${idx + 1 <= step ? "bg-clinic-primary" : "bg-slate-200"}`} />)}</div>
      <p className="mb-3 text-sm text-clinic-muted">{stepLabels[step - 1]}</p>
      {step === 1 && (
        <form className="space-y-3" onSubmit={form.handleSubmit(() => void sendSignupOtp())}>
          <Field label={t("auth.fullName")} required><input className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("fullName", { required: true })} /></Field>
          <Field label={t("auth.mobileNumber")} required><MobileInput value={signup.mobile} onChange={(v) => updateSignup({ mobile: v })} /></Field>
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
            <Field label={t("auth.opdStart")} required><input type="time" className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("opdStart", { required: true })} /></Field>
            <Field label={t("auth.opdEnd")} required><input type="time" className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("opdEnd", { required: true })} /></Field>
          </div>
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
            <button className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(3)}>{t("common.back")}</button>
            <button className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(5)}>{t("auth.skipForNow")}</button>
            <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => setStep(5)}>{t("auth.link")}</button>
          </div>
        </div>
      )}
      {step === 5 && (
        <div className="space-y-3">
          <label className="block rounded-xl border border-clinic-border p-3"><input type="radio" name="wa" checked={signup.whatsappChoice === "platform_default"} onChange={() => updateSignup({ whatsappChoice: "platform_default" })} /> {t("auth.waPlatformDefault")}</label>
          <label className="block rounded-xl border border-clinic-border p-3"><input type="radio" name="wa" checked={signup.whatsappChoice === "own_number"} onChange={() => updateSignup({ whatsappChoice: "own_number" })} /> {t("auth.waOwnNumber")}</label>
          <div className="flex justify-between gap-2">
            <button className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => setStep(4)}>{t("common.back")}</button>
            <button className="rounded-xl border border-clinic-border px-4 py-2" onClick={() => void finishSignup()}>{t("common.skip")}</button>
            <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => void finishSignup()}>{t("auth.finishSetup")}</button>
          </div>
        </div>
      )}
    </AuthCard>
  );
}
