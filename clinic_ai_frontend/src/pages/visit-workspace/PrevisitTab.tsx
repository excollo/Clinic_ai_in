import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useVisitStore } from "@/lib/visitStore";

export default function PrevisitTab({ onContinue }: { onContinue: () => void }) {
  const { t } = useTranslation();
  const chiefComplaint = useVisitStore((s) => s.chiefComplaint);
  const patientLanguage = t("previsit.patientLanguage");
  const hasIntake = !chiefComplaint.toLowerCase().includes("walk-in");
  const qa = useMemo(
    () => [
      { q: t("previsit.q1"), a: t("previsit.a1") },
      { q: t("previsit.q2"), a: t("previsit.a2") },
      { q: t("previsit.q3"), a: t("previsit.a3") },
    ],
    [],
  );
  useEffect(() => {
    void import("./VitalsTab");
  }, []);

  return (
    <div className="space-y-4">
      {hasIntake ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="clinic-card p-4">
            <p className="mb-1 text-xs text-clinic-muted">{t("previsit.chiefComplaint")}</p>
            <p className="text-lg font-semibold">{chiefComplaint}</p>
            <div className="mt-3 space-y-2 text-sm">
              <p><span className="text-clinic-muted">{t("previsit.history")}:</span> {t("previsit.historyValue")}</p>
              <p><span className="text-clinic-muted">{t("previsit.otherInfo")}:</span> {t("previsit.otherInfoValue")}</p>
            </div>
          </div>
          <div className="clinic-card p-4">
            <p className="mb-2 text-xs text-clinic-muted">{t("previsit.intakeQa")} · {patientLanguage}</p>
            <div className="max-h-56 space-y-3 overflow-y-auto pr-2">
              {qa.map((item) => (
                <div key={item.q}>
                  <p className="text-xs text-clinic-muted">{item.q}</p>
                  <p className="text-sm font-medium">{item.a}</p>
                </div>
              ))}
            </div>
            <button className="mt-2 text-xs text-clinic-primary">{t("previsit.viewAllAnswers")}</button>
          </div>
        </div>
      ) : (
        <div className="clinic-card p-4 text-sm">{t("previsit.noIntake")} · {chiefComplaint}</div>
      )}
      <div className="clinic-card p-4">
        <p className="mb-2 text-xs text-clinic-muted">{t("previsit.uploadedImages")}</p>
        <div className="flex gap-2">
          <div className="h-16 w-16 rounded-lg bg-slate-100" />
          <div className="h-16 w-16 rounded-lg bg-slate-100" />
        </div>
      </div>
      <div className="flex justify-end">
        <button onClick={onContinue} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("previsit.continueToVitals")}</button>
      </div>
    </div>
  );
}
