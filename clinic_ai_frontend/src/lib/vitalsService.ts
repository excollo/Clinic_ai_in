import apiClient from "@/lib/apiClient";
import { getMockVitalsRequiredFields } from "@/lib/mocks/vitalsRequiredFields";

export async function fetchVitalsRequiredFields(pid: string, vid: string, complaint: string) {
  if (import.meta.env.VITE_USE_MOCK_VITALS === "true") {
    return getMockVitalsRequiredFields(complaint);
  }
  const response = await apiClient.get(`/patients/${pid}/visits/${vid}/vitals/required-fields`);
  return response.data;
}
