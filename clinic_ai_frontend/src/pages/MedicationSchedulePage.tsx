import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

export default function MedicationSchedulePage() {
  const { t } = useTranslation();
  const { visitId } = useParams();
  const [editable, setEditable] = useState(false);
  const meds = [
    { name: t("medicationSchedule.med1Name"), summary: t("medicationSchedule.med1Summary"), slots: { morning: t("medicationSchedule.med1Morning"), afternoon: "", night: "" } },
    { name: t("medicationSchedule.med2Name"), summary: t("medicationSchedule.med2Summary"), slots: { morning: t("medicationSchedule.med2Morning"), afternoon: "", night: "" } },
  ];
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("medicationSchedule.title", { visitId })}</h2>
        <p className="text-sm text-clinic-muted">{t("medicationSchedule.subtitle")}</p>
      </div>
      {meds.map((med) => (
        <div key={med.name} className="clinic-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="font-semibold">{med.name}</p>
            <p className="text-sm text-clinic-muted">{med.summary}</p>
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            {(["morning", "afternoon", "night"] as const).map((slot) => {
              const val = med.slots[slot];
              return (
                <div key={slot} className={`rounded-xl border p-3 ${val ? "border-blue-200 bg-blue-50" : "border-dashed border-slate-300 bg-slate-50"}`}>
                  <p className="text-xs capitalize text-clinic-muted">{t(`medicationSchedule.slot.${slot}`)}</p>
                  {editable ? <input defaultValue={val} className="mt-1 w-full rounded border px-2 py-1 text-xs" /> : <p className="text-sm">{val || "-"}</p>}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <div className="rounded-xl bg-blue-50 p-3 text-sm text-blue-700">{t("medicationSchedule.reminderInfo")}</div>
      <div className="flex justify-end gap-2">
        <button onClick={() => setEditable(true)} className="rounded-xl border border-clinic-border px-4 py-2">{t("medicationSchedule.editTimes")}</button>
        <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("medicationSchedule.activateReminders")}</button>
      </div>
    </div>
  );
}
