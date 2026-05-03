import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useVisitStore } from "@/lib/visitStore";
import apiClient from "@/lib/apiClient";
import { toast } from "sonner";

export default function RecapTab({ approved }: { approved: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const visit = useVisitStore();
  const [sendTo, setSendTo] = useState<"patient" | "different" | "family">("patient");
  const [lang, setLang] = useState<"hindi" | "english" | "both">("hindi");
  const [recipient, setRecipient] = useState("");
  const [sending, setSending] = useState(false);
  const [previewPayload, setPreviewPayload] = useState<Record<string, unknown> | null>(null);

  const workspaceProgressQuery = useQuery({
    queryKey: ["workspace-progress", visit.patientId, visit.visitId],
    queryFn: async () => {
      const response = await apiClient.get(`/patients/${visit.patientId}/visits/${visit.visitId}/workspace-progress`);
      return response.data as { recap_sent?: boolean };
    },
    enabled: Boolean(visit.patientId && visit.visitId),
    staleTime: 60_000,
  });

  const extractErrorMessage = (error: unknown): string => {
    const maybe = error as {
      response?: { data?: { detail?: unknown; message?: unknown } };
      message?: unknown;
    };
    const detail = maybe?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail && typeof detail === "object") {
      const nested = detail as { detail?: unknown; message?: unknown; error?: unknown };
      if (typeof nested.detail === "string" && nested.detail.trim()) return nested.detail;
      if (typeof nested.message === "string" && nested.message.trim()) return nested.message;
      if (typeof nested.error === "string" && nested.error.trim()) return nested.error;
    }
    const message = maybe?.response?.data?.message;
    if (typeof message === "string" && message.trim()) return message;
    if (typeof maybe?.message === "string" && maybe.message.trim()) return maybe.message;
    return t("common.error");
  };

  const normalizeRecipientMobile = (value: string): string => {
    let digits = value.replace(/\D/g, "");
    if (digits.startsWith("91") && digits.length > 10) {
      digits = digits.slice(2);
    }
    if (digits.startsWith("0") && digits.length > 10) {
      digits = digits.slice(1);
    }
    if (digits.length > 10) {
      digits = digits.slice(-10);
    }
    return digits;
  };

  if (workspaceProgressQuery.data?.recap_sent) {
    return (
      <div className="clinic-card mx-auto max-w-lg space-y-4 p-8 text-center">
        <p className="text-sm text-[#1f3558]">{t("recap.alreadySent")}</p>
        <button
          type="button"
          onClick={() => navigate(`/visits/${visit.visitId}/recap-sent`)}
          className="rounded-xl bg-clinic-primary px-4 py-2 text-white"
        >
          {t("recap.viewConfirmation")}
        </button>
      </div>
    );
  }

  if (!approved) {
    return (
      <div className="clinic-card p-6 text-center">
        <p className="mb-2">{t("recap.blocked")}</p>
        <button onClick={() => useVisitStore.getState().setActiveTab("clinical_note")} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("recap.goClinical")}</button>
      </div>
    );
  }

  const preview = useMemo(() => {
    const payload = previewPayload;
    if (!payload) {
      const hello = lang === "english" ? t("recap.helloEnglish", { name: visit.patientName }) : t("recap.helloHindi", { name: visit.patientName });
      return `${hello}\n${t("recap.previewDiagnosis")}\n${t("recap.previewMedicines")}\n${t("recap.previewFollowUp")}\n${t("recap.previewWarnings")}\n${t("recap.previewFooter")}`;
    }
    const meds = Array.isArray(payload.medicines) ? payload.medicines : [];
    const tests = Array.isArray(payload.tests) ? payload.tests : [];
    const warnings = Array.isArray(payload.warning_signs) ? payload.warning_signs : [];
    const follow = (payload.follow_up as Record<string, string> | undefined) ?? {};
    return [
      String(payload.greeting ?? ""),
      String(payload.diagnosis ?? ""),
      meds.map((m) => `• ${(m as Record<string, string>).name ?? ""} ${(m as Record<string, string>).dose ?? ""}`).join("\n"),
      tests.map((x) => `• ${(x as Record<string, string>).test ?? ""}`).join("\n"),
      `${follow.date ?? ""} ${follow.instruction ?? ""}`.trim(),
      warnings.join(", "),
      String(payload.footer ?? ""),
    ].filter(Boolean).join("\n");
  }, [lang, previewPayload, t, visit.patientName]);

  const loadPreview = async (language: "hindi" | "english" | "both") => {
    try {
      const response = await apiClient.post("/patients/summary/postvisit", {
        visit_id: visit.visitId,
        patient_id: visit.patientId,
        language,
      });
      const payload = response.data?.whatsapp_payload ?? response.data?.payload ?? response.data;
      setPreviewPayload(payload as Record<string, unknown>);
    } catch {
      setPreviewPayload(null);
      toast.error(t("common.error"));
    }
  };

  const sendNow = async () => {
    const candidate = recipient || localStorage.getItem("clinic_mobile") || "";
    const recipientMobile = normalizeRecipientMobile(candidate);
    if (!/^[6-9]\d{9}$/.test(recipientMobile)) {
      toast.error(t("auth.mobileValidation"));
      return;
    }
    setSending(true);
    try {
      await apiClient.post("/whatsapp/send", {
        visit_id: visit.visitId,
        patient_id: visit.patientId,
        recipient_mobile: recipientMobile,
        language: lang,
        message_type: "post_visit_recap",
        template_variables: previewPayload ?? {},
      });
      await queryClient.invalidateQueries({ queryKey: ["workspace-progress", visit.patientId, visit.visitId] });
      navigate(`/visits/${visit.visitId}/recap-sent`);
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (approved) {
      void loadPreview(lang);
    }
  }, [approved, lang]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="space-y-3">
        <div className="clinic-card p-3">
          <label className="block"><input type="radio" checked={sendTo === "patient"} onChange={() => setSendTo("patient")} /> {t("recap.sendPatient")}</label>
          <label className="mt-2 block"><input type="radio" checked={sendTo === "different"} onChange={() => setSendTo("different")} /> {t("recap.sendDifferent")}</label>
          {sendTo === "different" && <input value={recipient} onChange={(e) => setRecipient(e.target.value)} className="mt-2 w-full rounded-lg border px-2 py-1" placeholder="+91" />}
          <label className="mt-2 block"><input type="radio" checked={sendTo === "family"} onChange={() => setSendTo("family")} /> {t("recap.sendFamily")}</label>
          {sendTo === "family" && <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3"><input className="rounded-lg border px-2 py-1" placeholder={t("recap.namePlaceholder")} /><select className="rounded-lg border px-2 py-1"><option>{t("recap.relationshipSpouse")}</option><option>{t("recap.relationshipSon")}</option><option>{t("recap.relationshipDaughter")}</option><option>{t("recap.relationshipOther")}</option></select><input className="rounded-lg border px-2 py-1" placeholder="+91" /></div>}
        </div>
        <div className="flex gap-2">
          {(["hindi", "english", "both"] as const).map((l) => (
            <button key={l} onClick={() => { setLang(l); void loadPreview(l); }} className={`rounded-full px-3 py-1 text-xs ${lang === l ? "bg-clinic-primary text-white" : "border border-clinic-border bg-white"}`}>{t(`recap.lang.${l.toLowerCase()}`)}</button>
          ))}
        </div>
      </div>
      <div className="clinic-card p-4">
        <div className="rounded-2xl bg-green-100 p-4 whitespace-pre-line text-sm">{preview}</div>
        <p className="mt-2 text-xs text-clinic-muted">{t("recap.caption")}</p>
      </div>
      <div className="col-span-full flex justify-end gap-2">
        <button className="rounded-xl border border-clinic-border px-4 py-2">{t("recap.saveForLater")}</button>
        <button onClick={() => void sendNow()} disabled={sending} className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50">{sending ? `${t("recap.sendNow")}...` : t("recap.sendNow")}</button>
      </div>
    </div>
  );
}
