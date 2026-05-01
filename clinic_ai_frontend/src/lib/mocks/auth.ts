import apiClient from "@/lib/apiClient";

export async function sendOtp(mobile: string): Promise<{ request_id: string; expires_in: number }> {
  const response = await apiClient.post("/auth/send-otp", { mobile });
  return response.data as { request_id: string; expires_in: number };
}

export async function verifyOtp(payload: { mobile: string; otp: string; request_id: string }) {
  const response = await apiClient.post("/auth/verify-otp", payload);
  return response.data;
}

export async function signupDoctor(payload: Record<string, unknown>) {
  const response = await apiClient.post("/auth/signup", payload);
  return response.data;
}

export async function loginDoctor(payload: { mobile: string; password: string }) {
  const response = await apiClient.post("/auth/login", payload);
  return response.data as { token: string; doctor_id: string; doctor_name: string };
}

export async function forgotPassword(payload: {
  mobile: string;
  otp: string;
  request_id: string;
  new_password: string;
}) {
  const response = await apiClient.post("/auth/forgot-password", payload);
  return response.data;
}
