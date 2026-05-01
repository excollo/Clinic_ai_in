import apiClient from "@/lib/apiClient";

export async function fetchConsentText(language: string) {
  const response = await apiClient.get("/consent/text", { params: { language, version: "latest" } });
  return String(response.data?.text ?? "");
}
