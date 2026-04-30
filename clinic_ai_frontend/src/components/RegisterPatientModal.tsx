import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { isValidIndianMobile, normalizeIndianMobile } from "@/lib/format";
import { registerPatient } from "@/lib/registrationService";

const schema = z.object({
  name: z.string().min(1),
  age: z.number().min(0).max(120),
  sex: z.enum(["male", "female", "other"]),
  mobile: z.string().refine(isValidIndianMobile),
  preferred_language: z.string().min(1),
  chief_complaint: z.string().min(1).max(200),
  schedule_date: z.string().optional(),
  schedule_time: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;
type SlotOption = { label: string; value: string; available: boolean };

function buildSlots(): SlotOption[] {
  const slots: SlotOption[] = [];
  for (let hour = 9; hour < 19; hour += 1) {
    for (let minute = 0; minute < 60; minute += 15) {
      const h12 = hour > 12 ? hour - 12 : hour;
      const ampm = hour >= 12 ? "PM" : "AM";
      const m = minute.toString().padStart(2, "0");
      slots.push({
        label: `${h12}:${m} ${ampm}`,
        value: `${hour.toString().padStart(2, "0")}:${m}`,
        available: true,
      });
    }
  }
  return slots;
}

export function RegisterPatientModal({
  open,
  onClose,
  onRegistered,
  initialWorkflow = "walk_in",
  initialSchedule,
}: {
  open: boolean;
  onClose: () => void;
  onRegistered?: () => void;
  initialWorkflow?: "walk_in" | "scheduled";
  initialSchedule?: { date?: string; time?: string };
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [workflow, setWorkflow] = useState<"walk_in" | "scheduled">(initialWorkflow);
  const slots = useMemo(() => buildSlots(), []);
  const { register, handleSubmit, formState: { errors, isValid, isSubmitting }, setValue, watch, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: { name: "", age: 0, sex: "male", mobile: "", preferred_language: "hindi", chief_complaint: "", schedule_date: initialSchedule?.date, schedule_time: initialSchedule?.time },
  });
  const mobile = watch("mobile");

  if (!open) return null;

  const doClose = () => {
    if (watch("name") || watch("mobile") || watch("chief_complaint")) {
      const ok = window.confirm(t("registration.confirmDiscard"));
      if (!ok) return;
    }
    reset();
    onClose();
  };

  const onSubmit = async (values: FormValues) => {
    const sex = values.sex === "male" ? "M" : values.sex === "female" ? "F" : "Other";
    const res = await registerPatient({
      name: values.name,
      age: values.age,
      sex,
      mobile: normalizeIndianMobile(values.mobile),
      language: values.preferred_language,
      chief_complaint: values.chief_complaint,
      workflow_type: workflow,
      scheduled_date: values.schedule_date,
      scheduled_time: values.schedule_time,
    });
    toast.success(t("registration.registered"));
    onRegistered?.();
    onClose();
    navigate(`/consent/${res.visit_id}`, { state: { ...res, patientName: values.name, patientLanguage: values.preferred_language, visitType: workflow } });
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <div className="clinic-card w-full max-w-2xl p-5">
        <div className="mb-4 flex items-center justify-between"><h2 className="text-h3">{t("registration.title")}</h2><button onClick={doClose}>X</button></div>
        <div className="mb-4 grid grid-cols-2 gap-3">
          <button onClick={() => setWorkflow("walk_in")} className={`rounded-xl border p-3 text-left ${workflow === "walk_in" ? "border-clinic-primary bg-indigo-50" : "border-clinic-border bg-white"}`}>{t("registration.walkIn")}</button>
          <button onClick={() => setWorkflow("scheduled")} className={`rounded-xl border p-3 text-left ${workflow === "scheduled" ? "border-clinic-primary bg-indigo-50" : "border-clinic-border bg-white"}`}>{t("registration.schedule")}</button>
        </div>
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
          <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("registration.namePlaceholder")} {...register("name")} />
          {errors.name && <p className="text-xs text-red-600">{t("common.required")}</p>}
          <div className="grid grid-cols-2 gap-3">
            <input type="number" className="rounded-xl border border-clinic-border px-3 py-2" placeholder={t("registration.agePlaceholder")} {...register("age", { valueAsNumber: true })} />
            <select className="rounded-xl border border-clinic-border px-3 py-2" {...register("sex")}><option value="male">{t("common.male")}</option><option value="female">{t("common.female")}</option><option value="other">{t("common.other")}</option></select>
          </div>
          <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("registration.mobilePlaceholder")} value={mobile} onChange={(e) => setValue("mobile", normalizeIndianMobile(e.target.value), { shouldValidate: true })} />
          <select className="w-full rounded-xl border border-clinic-border px-3 py-2" {...register("preferred_language")}><option value="hindi">{t("registration.hindi")}</option><option value="english">{t("registration.english")}</option><option value="marathi">{t("registration.marathi")}</option><option value="tamil">{t("registration.tamil")}</option><option value="telugu">{t("registration.telugu")}</option><option value="bengali">{t("registration.bengali")}</option><option value="kannada">{t("registration.kannada")}</option></select>
          <textarea className="w-full rounded-xl border border-clinic-border px-3 py-2" rows={2} placeholder={t("registration.chiefComplaintPlaceholder")} {...register("chief_complaint")} />
          {workflow === "walk_in" ? (
            <div className="rounded-xl bg-blue-50 p-3 text-sm text-blue-700">{t("registration.nextToken")}</div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <input type="date" className="rounded-xl border border-clinic-border px-3 py-2" {...register("schedule_date")} />
              <select className="rounded-xl border border-clinic-border px-3 py-2" {...register("schedule_time")}>
                <option value="">{t("registration.selectSlot")}</option>
                {slots.map((slot) => <option key={slot.value} value={slot.value} disabled={!slot.available}>{slot.label}{slot.available ? "" : " (taken)"}</option>)}
              </select>
            </div>
          )}
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={doClose} className="rounded-xl border border-clinic-border bg-white px-4 py-2">{t("common.cancel")}</button>
            <button disabled={!isValid || isSubmitting} className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50">{t("registration.continueToConsent")}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
