import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import apiClient from "@/lib/apiClient";

export default function AbhaScanSharePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState("");
  const [manual, setManual] = useState("");
  const [loading, setLoading] = useState(false);
  const [abdmUnavailable, setAbdmUnavailable] = useState(false);
  const [abdmMessage, setAbdmMessage] = useState("");

  const handleAbdmAvailabilityError = (err: unknown): boolean => {
    const status = (err as { response?: { status?: number; data?: { detail?: { status?: string; message?: string } | string } } })?.response?.status;
    const detail = (err as { response?: { data?: { detail?: { status?: string; message?: string } | string } } })?.response?.data?.detail;
    if (status === 503 && typeof detail === "object" && detail?.status === "abdm_not_configured") {
      setAbdmUnavailable(true);
      setAbdmMessage(detail.message || "ABDM integration is not configured for this clinic. Manual registration is available.");
      return true;
    }
    if (status === 501) {
      setAbdmUnavailable(true);
      setAbdmMessage("ABDM integration is pending on backend. Please use manual registration for now.");
      return true;
    }
    return false;
  };

  useEffect(() => {
    let scanner: { stop: () => void } | undefined;
    const init = async () => {
      try {
        await apiClient.post("/patients/abha/lookup", { abha_id: "00000000000000" });
      } catch (err) {
        if (handleAbdmAvailabilityError(err)) {
          return;
        }
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (videoRef.current) videoRef.current.srcObject = stream;
        const QrScanner = (await import("qr-scanner")).default;
        if (videoRef.current) {
          scanner = new QrScanner(videoRef.current, (result) => {
            setManual(typeof result === "string" ? result : result.data);
          });
          void scanner.start();
        }
      } catch {
        setError(t("abha.cameraDenied"));
      }
    };
    void init();
    return () => scanner?.stop();
  }, []);

  const submit = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post("/patients/abha/lookup", { abha_id: manual });
      navigate("/patients", { state: { prefill: response.data } });
    } catch (err) {
      if (!handleAbdmAvailabilityError(err)) {
        setError(t("common.error"));
      }
    } finally {
      setLoading(false);
    }
  };

  if (abdmUnavailable) {
    return (
      <div className="space-y-4">
        <h2 className="text-h2">{t("abha.title")}</h2>
        <div className="clinic-card p-6 text-center">
          <p className="text-lg font-semibold">ABDM not configured</p>
          <p className="mt-2 text-sm text-clinic-muted">
            {abdmMessage || "ABHA-based registration requires ABDM integration. Use manual registration instead."}
          </p>
          <button
            onClick={() => navigate("/patients")}
            className="mt-4 rounded-xl bg-clinic-primary px-4 py-2 text-white"
          >
            Register manually
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-h2">{t("abha.title")}</h2>
      <div className="clinic-card p-4">
        {error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : (
          <video ref={videoRef} autoPlay muted playsInline className="h-72 w-full rounded-xl bg-black object-cover" />
        )}
      </div>
      <div className="clinic-card p-4">
        <p className="mb-2 text-sm">{t("abha.manualEntry")}</p>
        <input value={manual} onChange={(e) => setManual(e.target.value.replace(/\D/g, "").slice(0, 14))} className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("abha.manualPlaceholder")} />
        <button disabled={manual.length < 14 || loading} onClick={() => void submit()} className="mt-3 rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50">{loading ? t("common.loading") : t("abha.useAbha")}</button>
      </div>
    </div>
  );
}
