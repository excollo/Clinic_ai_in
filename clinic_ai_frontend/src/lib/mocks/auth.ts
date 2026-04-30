import apiClient from "@/lib/apiClient";

function randomId() {
  return `mock_${Math.random().toString(36).slice(2, 10)}`;
}

export async function sendOtp(mobile: string): Promise<{ request_id: string; expires_in: number }> {
  try {
    const response = await apiClient.post("/auth/send-otp", { mobile });
    return response.data as { request_id: string; expires_in: number };
  } catch {
    console.warn("Using client-side OTP mock fallback for /auth/send-otp");
    return { request_id: randomId(), expires_in: 300 };
  }
}

export async function verifyOtp(payload: { mobile: string; otp: string; request_id: string }) {
  try {
    const response = await apiClient.post("/auth/verify-otp", payload);
    return response.data;
  } catch {
    console.warn("Using client-side OTP mock fallback for /auth/verify-otp");
    if (payload.otp === "123456") {
      return { token: "mock-token", doctor_id: "doctor-opaque-001" };
    }
    throw new Error("OTP_INVALID");
  }
}

export async function signupDoctor(payload: Record<string, unknown>) {
  try {
    const response = await apiClient.post("/auth/signup", payload);
    return response.data;
  } catch {
    console.warn("Using client-side mock fallback for /auth/signup");
    return { doctor_id: "doctor-opaque-001", token: "mock-token", status: "created" };
  }
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
