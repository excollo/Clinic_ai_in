import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { forgotPassword, sendOtp } from "@/lib/mocks/auth";
import { AuthCard, Field, MobileInput, OtpInput } from "@/features/auth/components";

export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  useDocumentTitle(`Forgot password · ${t("common.brand")}`);
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [mobile, setMobile] = useState("");
  const [requestId, setRequestId] = useState("");
  const [verifiedOtp, setVerifiedOtp] = useState("");
  const schema = z.object({ password: z.string().min(8), confirmPassword: z.string().min(8) }).refine((v) => v.password === v.confirmPassword);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), mode: "onBlur" });

  const handleSendOtp = async () => {
    const res = await sendOtp(mobile);
    setRequestId(res.request_id);
    setStep(2);
  };

  return (
    <AuthCard title={t("auth.forgotPassword")}>
      {step === 1 && (
        <div className="space-y-4">
          <Field label={t("auth.mobileNumber")} required><MobileInput autoFocus value={mobile} onChange={setMobile} /></Field>
          <button className="w-full rounded-xl bg-clinic-primary py-3 text-white" onClick={() => void handleSendOtp()}>{t("auth.sendOtp")}</button>
        </div>
      )}
      {step === 2 && <OtpInput mobile={mobile} requestId={requestId} onVerified={(otp) => { setVerifiedOtp(otp); setStep(3); }} />}
      {step === 3 && (
        <form className="space-y-4" onSubmit={form.handleSubmit(async (values) => {
          await forgotPassword({
            mobile,
            otp: verifiedOtp,
            request_id: requestId,
            new_password: values.password,
          });
          toast.success(t("auth.passwordResetSuccess"));
          navigate("/login");
        })}>
          <Field label={t("auth.newPassword")} required><input type="password" className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("password")} /></Field>
          <Field label={t("auth.confirmPassword")} required><input type="password" className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3" {...form.register("confirmPassword")} /></Field>
          <button className="w-full rounded-xl bg-clinic-primary py-3 text-white">{t("common.continue")}</button>
        </form>
      )}
    </AuthCard>
  );
}
