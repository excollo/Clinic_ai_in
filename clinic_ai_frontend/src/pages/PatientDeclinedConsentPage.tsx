import { useLocation, useNavigate } from "react-router-dom";

export default function PatientDeclinedConsentPage() {
  const navigate = useNavigate();
  const state = useLocation().state as { patientName?: string } | undefined;

  return (
    <div className="grid place-items-center">
      <div className="clinic-card w-full max-w-xl p-8 text-center">
        <h2 className="text-xl font-semibold">Patient declined consent</h2>
        <p className="mt-2 text-sm text-clinic-muted">
          {state?.patientName ? `${state.patientName} did not provide consent.` : "The patient did not provide consent."}
        </p>
        <p className="mt-1 text-sm text-clinic-muted">No consult workflow was advanced.</p>
        <div className="mt-5 flex justify-center gap-2">
          <button onClick={() => navigate(-1)} className="rounded-xl border border-clinic-border px-4 py-2">
            Try with different language
          </button>
          <button onClick={() => navigate("/patients")} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">
            Cancel registration
          </button>
        </div>
      </div>
    </div>
  );
}
