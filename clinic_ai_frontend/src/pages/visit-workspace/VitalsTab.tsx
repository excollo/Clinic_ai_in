import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { fetchVitalsRequiredFields } from "@/lib/vitalsService";
import { useVisitStore } from "@/lib/visitStore";
import apiClient from "@/lib/apiClient";

type DynamicField = {
  key: string;
  label: string;
  type: string;
  unit: string;
  normal_range: [number, number] | null;
};

export default function VitalsTab({ onSkip, onSaved }: { onSkip: () => void; onSaved: () => void }) {
  const { t } = useTranslation();
  const [saved, setSaved] = useState(false);
  const visit = useVisitStore();
  const form = useForm({ mode: "onBlur", defaultValues: { systolic: "", diastolic: "", weight: "" } });
  const vitalsQuery = useQuery({
    queryKey: ["vitals-required", visit.visitId, visit.patientId, visit.chiefComplaint],
    queryFn: () => fetchVitalsRequiredFields(visit.patientId, visit.visitId, visit.chiefComplaint),
    retry: 0,
  });

  const fields: DynamicField[] = useMemo(
    () => (vitalsQuery.data?.dynamic_fields as DynamicField[] | undefined) ?? [],
    [vitalsQuery.data],
  );

  const save = async (values: Record<string, unknown>) => {
    const payload = {
      blood_pressure: {
        systolic: Number(values.systolic || 0),
        diastolic: Number(values.diastolic || 0),
      },
      weight: Number(values.weight || 0),
      dynamic_values: fields.reduce<Record<string, number>>((acc, field) => {
        const value = Number(values[field.key] || 0);
        if (!Number.isNaN(value) && value > 0) acc[field.key] = value;
        return acc;
      }, {}),
    };
    try {
      await apiClient.post(`/patients/${visit.patientId}/visits/${visit.visitId}/vitals`, payload);
      setSaved(true);
      onSaved();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        toast.error(t("vitals.alreadyRecorded"));
      } else {
        toast.error(t("common.error"));
      }
    }
  };

  const systolic = Number(form.watch("systolic") || 0);

  return (
    <form className="space-y-4" onSubmit={form.handleSubmit((values) => void save(values as Record<string, unknown>))}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{t("vitals.title")}</h3>
          <p className="text-xs text-clinic-muted">{t("vitals.subtitle")}</p>
        </div>
        {saved && <span className="rounded-full bg-green-100 px-3 py-1 text-xs text-green-700">{t("vitals.saved")}</span>}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="clinic-card p-3">
          <p className="text-sm">{t("vitals.bloodPressure")}</p>
          {saved ? <p>{form.getValues("systolic")}/{form.getValues("diastolic")} mmHg</p> : <div className="mt-2 flex gap-2"><input className="w-full rounded-lg border px-2 py-1" {...form.register("systolic")} /><input className="w-full rounded-lg border px-2 py-1" {...form.register("diastolic")} /></div>}
          {!saved && systolic > 140 && <p className="mt-1 text-xs text-amber-700">{t("vitals.bpHigh")}</p>}
          {!saved && systolic > 0 && systolic < 90 && <p className="mt-1 text-xs text-red-700">{t("vitals.bpLow")}</p>}
        </div>
        <div className="clinic-card p-3">
          <p className="text-sm">{t("vitals.weight")}</p>
          {saved ? <p>{form.getValues("weight")} kg</p> : <input className="mt-2 w-full rounded-lg border px-2 py-1" {...form.register("weight")} />}
        </div>
      </div>

      {vitalsQuery.isLoading && (
        <div>
          <p className="mb-2 text-xs text-clinic-muted">{t("vitals.aiSuggested")}</p>
          <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-lg bg-slate-100" />)}</div>
        </div>
      )}
      {vitalsQuery.isError && <p className="text-sm text-clinic-muted">{t("vitals.additionalUnavailable")}</p>}
      {!vitalsQuery.isLoading && !vitalsQuery.isError && fields.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-clinic-muted">{t("vitals.aiSuggested")}</p>
          {fields.map((f) => {
            const value = Number(form.watch(f.key as "systolic") || 0);
            const range = f.normal_range;
            const out = Array.isArray(range) && value > 0 && (value < range[0] || value > range[1]);
            return (
              <div key={f.key} className="clinic-card p-3">
                <p className="text-sm">{f.label} ({f.unit})</p>
                {saved ? <p>{String(form.getValues(f.key as "systolic"))} {f.unit}</p> : <input className="mt-2 w-full rounded-lg border px-2 py-1" {...form.register(f.key as "systolic")} />}
                {Array.isArray(range) && <p className="mt-1 text-xs text-clinic-muted">{range[0]}-{range[1]} {f.unit}</p>}
                {out && Array.isArray(range) && <p className="text-xs text-amber-700">{t("vitals.aboveRange", { min: range[0], max: range[1], unit: f.unit })}</p>}
              </div>
            );
          })}
        </div>
      )}
      <div className="flex items-center justify-between">
        <button type="button" onClick={onSkip} className="text-sm text-clinic-primary">{t("vitals.skipVitals")}</button>
        <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("vitals.saveContinue")}</button>
      </div>
    </form>
  );
}
