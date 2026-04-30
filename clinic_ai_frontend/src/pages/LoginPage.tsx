import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/lib/authStore";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { isValidIndianMobile } from "@/lib/format";
import { AuthCard, Field, MobileInput } from "@/features/auth/components";
import { loginDoctor } from "@/lib/mocks/auth";
import { toast } from "sonner";

export default function LoginPage() {
  const { t } = useTranslation();
  useDocumentTitle(`Sign in · ${t("common.brand")}`);
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const schema = z.object({
    mobile: z.string().refine(isValidIndianMobile, t("auth.mobileValidation")),
    password: z.string().min(8, t("auth.requiredField")),
  });
  const { handleSubmit, setValue, watch, register, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: { mobile: "", password: "" },
  });
  const mobile = watch("mobile");
  const prefetchDashboard = () => {
    void import("@/pages/DashboardPage");
  };

  const onSubmit = async (data: z.infer<typeof schema>) => {
    try {
      const response = await loginDoctor({ mobile: data.mobile, password: data.password });
      setSession({
        apiKey: response.token,
        doctorId: response.doctor_id,
        doctorName: response.doctor_name,
        mobile: data.mobile,
      });
      navigate("/dashboard");
    } catch {
      toast.error(t("auth.otpInvalid"));
    }
  };

  return (
    <AuthCard title={t("auth.signIn")}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Field label={t("auth.mobileNumber")} required error={errors.mobile?.message}><MobileInput autoFocus value={mobile} onChange={(v) => setValue("mobile", v, { shouldValidate: true })} /></Field>
        <Field label={t("auth.password")} required error={errors.password?.message}><input type="password" className="focus-ring w-full rounded-xl border border-clinic-border px-3 py-3 text-sm" onBlur={prefetchDashboard} {...register("password")} /></Field>
        <button type="button" className="text-xs text-clinic-primary" onClick={() => navigate("/forgot-password")}>{t("auth.forgotPassword")}</button>
        <button className="w-full rounded-xl bg-clinic-primary py-3 text-sm font-semibold text-white">{isSubmitting ? t("auth.signingIn") : t("auth.signIn")}</button>
      </form>
      <p className="mt-4 text-center text-sm text-clinic-muted">{t("auth.createAccountPrompt")} <button className="text-clinic-primary" onClick={() => navigate("/signup")}>{t("auth.createAccount")}</button></p>
    </AuthCard>
  );
}
