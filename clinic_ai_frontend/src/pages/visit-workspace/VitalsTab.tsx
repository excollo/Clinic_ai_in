import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { fetchVitalsRequiredFields } from "@/lib/vitalsService";
import { useVisitStore } from "@/lib/visitStore";
import apiClient from "@/lib/apiClient";

/** Keys handled as fixed BP + weight everywhere (never repeated in dynamic list). Mirrors backend FIXED_FIELDS semantics. */
const FIXED_VITAL_KEYS = new Set(["blood_pressure", "weight"]);

type DynamicField = {
  key: string;
  label: string;
  type: string;
  unit: string;
  normal_range: [number, number] | null;
  ai_reason?: string;
};

type FixedFieldRaw = {
  key: string;
  label: string;
  type: string;
  unit: string;
  normal_range?: unknown;
};

function isBpNormalRange(v: unknown): v is { systolic: [number, number]; diastolic: [number, number] } {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  const s = o.systolic;
  const d = o.diastolic;
  return (
    Array.isArray(s) &&
    s.length === 2 &&
    typeof s[0] === "number" &&
    typeof s[1] === "number" &&
    Array.isArray(d) &&
    d.length === 2 &&
    typeof d[0] === "number" &&
    typeof d[1] === "number"
  );
}

/** Default when `/vitals/required-fields` omits fixed_fields — matches clinic_ai_backend `FIXED_FIELDS`. */
const FALLBACK_FIXED_FIELDS: FixedFieldRaw[] = [
  {
    key: "blood_pressure",
    label: "Blood pressure",
    type: "bp_pair",
    unit: "mmHg",
    normal_range: { systolic: [90, 130], diastolic: [60, 85] },
  },
  { key: "weight", label: "Weight", type: "number", unit: "kg", normal_range: null },
];

type StoredVitals = {
  blood_pressure?: { systolic?: number; diastolic?: number };
  weight?: number;
  dynamic_values?: Record<string, number>;
};

type WorkspaceProgressVitals = {
  vitals_recorded?: boolean;
  vitals?: StoredVitals | null;
};

export default function VitalsTab({ onSkip, onSaved }: { onSkip: () => void; onSaved: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const visit = useVisitStore();
  const form = useForm({ mode: "onBlur", defaultValues: { systolic: "", diastolic: "", weight: "" } });
  const workspaceQuery = useQuery({
    queryKey: ["workspace-progress", visit.patientId, visit.visitId],
    queryFn: async () => {
      const response = await apiClient.get(`/patients/${visit.patientId}/visits/${visit.visitId}/workspace-progress`);
      return response.data as WorkspaceProgressVitals;
    },
    enabled: Boolean(visit.patientId && visit.visitId),
    staleTime: 60_000,
  });
  const vitalsQuery = useQuery({
    queryKey: ["vitals-required", visit.visitId, visit.patientId, visit.chiefComplaint],
    queryFn: () => fetchVitalsRequiredFields(visit.patientId, visit.visitId, visit.chiefComplaint),
    retry: 0,
  });

  const fixedFields: FixedFieldRaw[] = useMemo(() => {
    const raw = vitalsQuery.data?.fixed_fields as FixedFieldRaw[] | undefined;
    if (raw?.some((f) => f?.key === "blood_pressure")) {
      return raw;
    }
    return FALLBACK_FIXED_FIELDS;
  }, [vitalsQuery.data?.fixed_fields]);

  const bpFixed = useMemo(() => fixedFields.find((f) => f.key === "blood_pressure"), [fixedFields]);
  const weightFixed = useMemo(() => fixedFields.find((f) => f.key === "weight"), [fixedFields]);
  const bpNormalGuide = useMemo((): { systolic: [number, number]; diastolic: [number, number] } => {
    if (bpFixed && isBpNormalRange(bpFixed.normal_range)) {
      return bpFixed.normal_range;
    }
    const fb = FALLBACK_FIXED_FIELDS[0];
    if (isBpNormalRange(fb?.normal_range)) return fb.normal_range;
    return { systolic: [90, 130], diastolic: [60, 85] };
  }, [bpFixed]);

  const dynamicFields: DynamicField[] = useMemo(() => {
    const raw = (vitalsQuery.data?.dynamic_fields as DynamicField[] | undefined) ?? [];
    return raw.filter((f) => f?.key && !FIXED_VITAL_KEYS.has(String(f.key).toLowerCase()));
  }, [vitalsQuery.data?.dynamic_fields]);

  const complaintProcessed = vitalsQuery.data?.complaint_processed as string | undefined;

  useEffect(() => {
    const progress = workspaceQuery.data;
    if (!progress?.vitals_recorded) return;

    const applyPayload = (doc: StoredVitals) => {
      const dyn = doc.dynamic_values ?? {};
      const base: Record<string, string> = {
        systolic: String(doc.blood_pressure?.systolic ?? ""),
        diastolic: String(doc.blood_pressure?.diastolic ?? ""),
        weight: String(doc.weight ?? ""),
      };
      fields.forEach((f) => {
        base[f.key] = String(dyn[f.key] ?? "");
      });
      Object.keys(dyn).forEach((k) => {
        if (base[k] === undefined) base[k] = String(dyn[k] ?? "");
      });
      form.reset(base);
      setSaved(true);
    };

    if (progress.vitals) {
      applyPayload(progress.vitals);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const response = await apiClient.get(`/patients/${visit.patientId}/visits/${visit.visitId}/vitals`);
        if (cancelled) return;
        applyPayload(response.data as StoredVitals);
      } catch {
        setSaved(true);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- form.reset is stable; re-run when field definitions load
  }, [workspaceQuery.data, dynamicFields, visit.patientId, visit.visitId]);

  const save = async (values: Record<string, unknown>) => {
    const payload = {
      blood_pressure: {
        systolic: Number(values.systolic || 0),
        diastolic: Number(values.diastolic || 0),
      },
      weight: Number(values.weight || 0),
      dynamic_values: dynamicFields.reduce<Record<string, number>>((acc, field) => {
        const value = Number(values[field.key] || 0);
        if (!Number.isNaN(value) && value > 0) acc[field.key] = value;
        return acc;
      }, {}),
    };
    try {
      await apiClient.post(`/patients/${visit.patientId}/visits/${visit.visitId}/vitals`, payload);
      await queryClient.invalidateQueries({ queryKey: ["workspace-progress", visit.patientId, visit.visitId] });
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
  const diastolic = Number(form.watch("diastolic") || 0);
  const bpUnit = bpFixed?.unit ?? "mmHg";
  const weightUnit = weightFixed?.unit ?? "kg";
  const bpOutOfRange =
    !saved &&
    ((systolic > 0 && (systolic < bpNormalGuide.systolic[0] || systolic > bpNormalGuide.systolic[1])) ||
      (diastolic > 0 && (diastolic < bpNormalGuide.diastolic[0] || diastolic > bpNormalGuide.diastolic[1])));

  return (
    <form className="space-y-4" onSubmit={form.handleSubmit((values) => void save(values as Record<string, unknown>))}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{t("vitals.title")}</h3>
          <p className="text-xs text-clinic-muted">{t("vitals.subtitle")}</p>
          {vitalsQuery.isSuccess &&
            complaintProcessed !== undefined &&
            complaintProcessed !== "" &&
            complaintProcessed !== "general" && (
              <p className="mt-1 text-xs text-clinic-muted">{t("vitals.complaintContext", { complaint: complaintProcessed })}</p>
            )}
        </div>
        {saved && <span className="rounded-full bg-green-100 px-3 py-1 text-xs text-green-700">{t("vitals.saved")}</span>}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="clinic-card p-3">
          <p className="text-sm">{bpFixed?.label ?? t("vitals.bloodPressure")}</p>
          {saved ? (
            <p>{form.getValues("systolic")}/{form.getValues("diastolic")} {bpUnit}</p>
          ) : (
            <div className="mt-2 flex gap-2">
              <input className="w-full rounded-lg border px-2 py-1" {...form.register("systolic")} />
              <input className="w-full rounded-lg border px-2 py-1" {...form.register("diastolic")} />
            </div>
          )}
          {!saved && (
            <p className="mt-1 text-xs text-clinic-muted">
              {t("vitals.bpGuideline", {
                sMin: bpNormalGuide.systolic[0],
                sMax: bpNormalGuide.systolic[1],
                dMin: bpNormalGuide.diastolic[0],
                dMax: bpNormalGuide.diastolic[1],
                unit: bpUnit,
              })}
            </p>
          )}
          {bpOutOfRange && (
            <p className="mt-1 text-xs text-amber-700">
              {t("vitals.bpOutOfGuideline", {
                sLo: bpNormalGuide.systolic[0],
                sHi: bpNormalGuide.systolic[1],
                dLo: bpNormalGuide.diastolic[0],
                dHi: bpNormalGuide.diastolic[1],
                unit: bpUnit,
              })}
            </p>
          )}
        </div>
        <div className="clinic-card p-3">
          <p className="text-sm">{weightFixed?.label ?? t("vitals.weight")}</p>
          {saved ? <p>{form.getValues("weight")} {weightUnit}</p> : <input className="mt-2 w-full rounded-lg border px-2 py-1" {...form.register("weight")} />}
        </div>
      </div>

      {vitalsQuery.isLoading && (
        <div>
          <p className="mb-2 text-xs text-clinic-muted">{t("vitals.aiSuggested")}</p>
          <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-10 animate-pulse rounded-lg bg-slate-100" />)}</div>
        </div>
      )}
      {vitalsQuery.isError && <p className="text-sm text-clinic-muted">{t("vitals.additionalUnavailable")}</p>}
      {!vitalsQuery.isLoading && !vitalsQuery.isError && dynamicFields.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-clinic-muted">{t("vitals.aiSuggested")}</p>
          {dynamicFields.map((f) => {
            const value = Number(form.watch(f.key) || 0);
            const range = f.normal_range;
            const out = Array.isArray(range) && value > 0 && (value < range[0] || value > range[1]);
            return (
              <div key={f.key} className="clinic-card p-3">
                <p className="text-sm">{f.label} ({f.unit})</p>
                {f.ai_reason ? <p className="mt-0.5 text-xs text-clinic-muted">{f.ai_reason}</p> : null}
                {saved ? <p>{String(form.getValues(f.key))} {f.unit}</p> : <input className="mt-2 w-full rounded-lg border px-2 py-1" {...form.register(f.key)} />}
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
