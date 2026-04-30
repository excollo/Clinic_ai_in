import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { lookupAbhaMock } from "@/lib/mocks/abha";

export default function AbhaScanSharePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState("");
  const [manual, setManual] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let scanner: { stop: () => void } | undefined;
    const init = async () => {
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
    const data = await lookupAbhaMock(manual);
    setLoading(false);
    navigate("/patients", { state: { prefill: data } });
  };

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
