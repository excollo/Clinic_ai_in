import { lazy, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

const ProfileTab = lazy(() => import("./settings-tabs/ProfileTab"));
const ClinicTab = lazy(() => import("./settings-tabs/ClinicTab"));
const WhatsAppTemplatesTab = lazy(() => import("./settings-tabs/WhatsAppTemplatesTab"));
const AIPreferencesTab = lazy(() => import("./settings-tabs/AIPreferencesTab"));
const LanguagesTab = lazy(() => import("./settings-tabs/LanguagesTab"));
const ABDMTab = lazy(() => import("./settings-tabs/ABDMTab"));
const AuditLogTab = lazy(() => import("./settings-tabs/AuditLogTab"));
const ManageStaffTab = lazy(() => import("./settings-tabs/ManageStaffTab"));

export default function SettingsPage() {
  const { t } = useTranslation();
  const tabs = [
    { key: "profile", label: t("settings.tabProfile") },
    { key: "clinic", label: t("settings.tabClinic") },
    { key: "templates", label: t("settings.tabTemplates") },
    { key: "ai-preferences", label: t("settings.tabAiPreferences") },
    { key: "languages", label: t("settings.tabLanguages") },
    { key: "abdm", label: t("settings.tabAbdm") },
    { key: "audit-log", label: t("settings.tabAuditLog") },
    { key: "manage-staff", label: t("settings.tabManageStaff") },
  ] as const;
  const [saving, setSaving] = useState(false);
  const [search] = useSearchParams();
  const [active, setActive] = useState(search.get("tab") ?? "profile");
  const Tab = useMemo(() => {
    if (active === "clinic") return ClinicTab;
    if (active === "templates") return WhatsAppTemplatesTab;
    if (active === "ai-preferences") return AIPreferencesTab;
    if (active === "languages") return LanguagesTab;
    if (active === "abdm") return ABDMTab;
    if (active === "audit-log") return AuditLogTab;
    if (active === "manage-staff") return ManageStaffTab;
    return ProfileTab;
  }, [active]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("settings.title")}</h2>
        <p className="text-sm text-clinic-muted">{t("settings.subtitle")}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button key={tab.key} onClick={() => setActive(tab.key)} className={`rounded-full px-3 py-1 text-xs ${active === tab.key ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>{tab.label}</button>
        ))}
      </div>
      <div className="clinic-card p-4">
        <Suspense fallback={<div className="h-20 animate-pulse rounded-xl bg-slate-100" />}>
          <Tab />
        </Suspense>
      </div>
      <div className="flex justify-end">
        <button
          onClick={async () => {
            setSaving(true);
            await new Promise((resolve) => setTimeout(resolve, 150));
            setSaving(false);
            toast.info("Settings save API is not connected yet.");
          }}
          className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50"
          disabled={saving}
        >
          {saving ? t("settings.saving") : t("common.saveChanges")}
        </button>
      </div>
    </div>
  );
}
