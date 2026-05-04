import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/apiClient";

export type PatientRecord = {
  id: string;
  patient_id: string;
  name: string;
  age: number;
  sex: "male" | "female" | "other";
  mobile: string;
  visitCount: number;
  lastSeen: string;
  chronic: boolean;
  abhaLinked: boolean;
  language: string;
};

type RawPatient = {
  patient_id?: string;
  id?: string;
  name?: string;
  full_name?: string;
  age?: number | null;
  sex?: string | null;
  gender?: string | null;
  mobile?: string | null;
  phone_number?: string | null;
  language?: string | null;
  preferred_language?: string | null;
  abha_id?: string | null;
  visit_count?: number | null;
  last_visit_date?: string | null;
  chronic_conditions?: string[] | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ApiPatientsResponse = {
  patients?: RawPatient[];
  total?: number;
  limit?: number;
  offset?: number;
};

export const PATIENT_LIST_PAGE_SIZE = 10;

function normalizeSex(value: string | null | undefined): PatientRecord["sex"] {
  const v = String(value || "").toLowerCase();
  if (v === "m" || v === "male") return "male";
  if (v === "f" || v === "female") return "female";
  return "other";
}

function normalizePatient(raw: RawPatient): PatientRecord {
  const name = String(raw.name || raw.full_name || "unknown").trim();
  const lastSeen = String(raw.last_visit_date || raw.updated_at || raw.created_at || new Date().toISOString());
  const chronicConditions = Array.isArray(raw.chronic_conditions) ? raw.chronic_conditions : [];
  const pid = String(raw.patient_id || raw.id || "");
  return {
    id: pid,
    patient_id: pid,
    name,
    age: Number(raw.age || 0),
    sex: normalizeSex(raw.sex || raw.gender),
    mobile: String(raw.mobile || raw.phone_number || ""),
    visitCount: Number(raw.visit_count || 0),
    lastSeen,
    chronic: chronicConditions.length > 0,
    abhaLinked: Boolean(raw.abha_id),
    language: String(raw.language || raw.preferred_language || "english"),
  };
}

/** Map UI multi-filter to single contract `filter` query param. */
function resolveListFilter(filters: string[]): string {
  if (filters.includes("all") || filters.length === 0) return "all";
  const order = ["abha", "chronic", "last30"];
  for (const key of order) {
    if (filters.includes(key)) return key;
  }
  return "all";
}

export async function fetchPatientsPageReal(params: {
  offset: number;
  limit: number;
  search: string;
  filters: string[];
}) {
  const filter = resolveListFilter(params.filters);
  const response = await apiClient.get("/patients", {
    params: {
      limit: params.limit,
      offset: params.offset,
      search: params.search,
      filter,
    },
  });
  const body = response.data as ApiPatientsResponse | RawPatient[];
  const list = Array.isArray(body)
    ? (body as RawPatient[])
    : Array.isArray((body as ApiPatientsResponse).patients)
      ? ((body as ApiPatientsResponse).patients as RawPatient[])
      : [];
  const total =
    typeof body === "object" && body !== null && !Array.isArray(body) && "total" in body
      ? Number((body as ApiPatientsResponse).total ?? list.length)
      : list.length;
  const normalized = list.map(normalizePatient);
  return {
    data: normalized,
    total,
    hasMore: params.offset + normalized.length < total,
  };
}

export function usePatients(search: string, filters: string[], page: number) {
  return useQuery({
    queryKey: ["patients", search, filters.join(","), page],
    queryFn: () =>
      fetchPatientsPageReal({
        offset: page * PATIENT_LIST_PAGE_SIZE,
        limit: PATIENT_LIST_PAGE_SIZE,
        search,
        filters,
      }),
  });
}
