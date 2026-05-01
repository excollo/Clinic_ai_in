import { useLocation, useNavigate } from "react-router-dom";
import { RegisterPatientModal } from "@/components/RegisterPatientModal";

export default function RegisterPatientPage() {
  const navigate = useNavigate();
  const state = useLocation().state as
    | {
        initialWorkflow?: "walk_in" | "scheduled";
        initialSchedule?: { date?: string; time?: string };
      }
    | undefined;

  return (
    <RegisterPatientModal
      asPage
      onClose={() => navigate(-1)}
      initialWorkflow={state?.initialWorkflow ?? "walk_in"}
      initialSchedule={state?.initialSchedule}
    />
  );
}
