import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem("clinic_api_key");
  const doctorId = localStorage.getItem("clinic_doctor_id");
  if (apiKey) {
    config.headers["X-API-Key"] = apiKey;
  }
  if (doctorId) {
    config.headers["X-Doctor-ID"] = doctorId;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("clinic_api_key");
      localStorage.removeItem("clinic_doctor_id");
      localStorage.removeItem("clinic_doctor_name");
      localStorage.removeItem("clinic_mobile");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default apiClient;
