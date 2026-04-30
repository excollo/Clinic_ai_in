import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function WhatsAppTemplatesTab() {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<string | null>(null);
  return (
    <div className="space-y-2">
      {[t("settings.templateVisitRecap"), t("settings.templateLabSummary"), t("settings.templateFollowup")].map((template) => (
        <div key={template} className="flex items-center justify-between rounded-xl border border-clinic-border bg-white p-3">
          <span>{template}</span>
          <button className="rounded-lg border px-3 py-1" onClick={() => setPreview(template)}>
            {t("settings.templatePreview")}
          </button>
        </div>
      ))}
      {preview && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="font-semibold">{preview}</p>
              <button onClick={() => setPreview(null)} aria-label={t("settings.closePreview")}>X</button>
            </div>
            <div className="rounded-2xl bg-green-100 p-4 text-sm">{t("settings.templatePreviewMessage")}</div>
          </div>
        </div>
      )}
    </div>
  );
}
