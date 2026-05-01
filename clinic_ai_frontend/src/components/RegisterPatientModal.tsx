import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { isValidIndianMobile, normalizeIndianMobile } from "@/lib/format";
import { registerPatient } from "@/lib/registrationService";

const schema = z.object({
  visit_type: z.enum(["walk_in", "scheduled"]),
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  age: z.number().min(0).max(120),
  sex: z.enum(["male", "female", "other"]),
  mobile: z.string().refine(isValidIndianMobile),
  preferred_language: z.string().min(1),
  appointment_date: z.string().optional(),
  appointment_time: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function RegisterPatientModal({
  open,
  onClose,
  onRegistered,
  initialWorkflow = "walk_in",
  initialSchedule,
  asPage = false,
}: {
  open?: boolean;
  onClose: () => void;
  onRegistered?: () => void;
  initialWorkflow?: "walk_in" | "scheduled";
  initialSchedule?: { date?: string; time?: string };
  asPage?: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isValid, isSubmitting }, setValue, watch, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: {
      visit_type: initialWorkflow,
      first_name: "",
      last_name: "",
      age: 0,
      sex: "male",
      mobile: "",
      preferred_language: "hindi",
      appointment_date: initialSchedule?.date,
      appointment_time: initialSchedule?.time,
    },
  });
  const mobile = watch("mobile");

  if (!asPage && !open) return null;

  const doClose = () => {
    if (watch("first_name") || watch("last_name") || watch("mobile")) {
      const ok = window.confirm(t("registration.confirmDiscard"));
      if (!ok) return;
    }
    reset();
    onClose();
  };

  const onSubmit = async (values: FormValues) => {
    const sex = values.sex === "male" ? "M" : values.sex === "female" ? "F" : "Other";
    const workflow = values.visit_type;
    const now = new Date();
    const fallbackDate = now.toISOString().slice(0, 10);
    const fallbackTime = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    const res = await registerPatient({
      name: `${values.first_name} ${values.last_name}`.trim(),
      age: values.age,
      sex,
      mobile: normalizeIndianMobile(values.mobile),
      language: values.preferred_language,
      chief_complaint: "General consultation",
      workflow_type: workflow,
      scheduled_date: values.appointment_date || fallbackDate,
      scheduled_time: values.appointment_time || fallbackTime,
    });
    toast.success(t("registration.registered"));
    if (workflow === "scheduled") {
      if (res.whatsapp_triggered) {
        toast.success("WhatsApp intake triggered.");
      } else {
        toast.warning("Appointment created, but WhatsApp intake was not triggered.");
      }
    }
    onRegistered?.();
    onClose();
    navigate(`/consent/${res.visit_id}`, {
      state: {
        ...res,
        patientName: `${values.first_name} ${values.last_name}`.trim(),
        patientLanguage: values.preferred_language,
        visitType: workflow,
      },
    });
  };

  return (
    <div className={asPage ? "mx-auto w-full max-w-4xl p-4 md:p-6" : "fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"}>
      <div className={`clinic-card w-full ${asPage ? "p-5 md:p-6" : "max-w-2xl p-5"}`}>
        <div className="mb-4 flex items-center justify-between"><h2 className="text-h3">{t("registration.title")}</h2><button onClick={doClose}>X</button></div>
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
          <select className="w-full rounded-xl border border-clinic-border px-3 py-2" {...register("visit_type")}>
            <option value="walk_in">Walk in visit</option>
            <option value="scheduled">Schedule visit</option>
          </select>
          <div className="grid grid-cols-2 gap-3">
            <input className="rounded-xl border border-clinic-border px-3 py-2" placeholder="First name" {...register("first_name")} />
            <input className="rounded-xl border border-clinic-border px-3 py-2" placeholder="Last name" {...register("last_name")} />
          </div>
          {(errors.first_name || errors.last_name) && <p className="text-xs text-red-600">{t("common.required")}</p>}
          <div className="grid grid-cols-2 gap-3">
            <input type="number" className="rounded-xl border border-clinic-border px-3 py-2" placeholder={t("registration.agePlaceholder")} {...register("age", { valueAsNumber: true })} />
            <select className="rounded-xl border border-clinic-border px-3 py-2" {...register("sex")}><option value="male">{t("common.male")}</option><option value="female">{t("common.female")}</option><option value="other">{t("common.other")}</option></select>
          </div>
          <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("registration.mobilePlaceholder")} value={mobile} onChange={(e) => setValue("mobile", normalizeIndianMobile(e.target.value), { shouldValidate: true })} />
          <select className="w-full rounded-xl border border-clinic-border px-3 py-2" {...register("preferred_language")}><option value="hindi">{t("registration.hindi")}</option><option value="english">{t("registration.english")}</option><option value="marathi">{t("registration.marathi")}</option><option value="tamil">{t("registration.tamil")}</option><option value="telugu">{t("registration.telugu")}</option><option value="bengali">{t("registration.bengali")}</option><option value="kannada">{t("registration.kannada")}</option></select>
          <div className="grid grid-cols-2 gap-3">
            <input type="date" className="rounded-xl border border-clinic-border px-3 py-2" {...register("appointment_date")} />
            <input type="time" className="rounded-xl border border-clinic-border px-3 py-2" {...register("appointment_time")} />
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={doClose} className="rounded-xl border border-clinic-border bg-white px-4 py-2">{t("common.cancel")}</button>
            <button disabled={!isValid || isSubmitting} className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50">{t("registration.continueToConsent")}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
