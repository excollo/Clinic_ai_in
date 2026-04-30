import { useInfiniteQuery } from "@tanstack/react-query";
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

type RealPatientsResponse = {
  patients: RawPatient[];
  total: number;
  limit: number;
  offset: number;
};

const PAGE_SIZE = 20;

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

function applyClientFilters(
  patients: PatientRecord[],
  search: string,
  filters: string[],
): PatientRecord[] {
  const q = search.trim().toLowerCase();
  let filtered = patients;
  if (q) {
    filtered = filtered.filter((p) => p.name.toLowerCase().includes(q) || p.mobile.includes(q));
  }
  if (filters.includes("chronic")) filtered = filtered.filter((p) => p.chronic);
  if (filters.includes("abha")) filtered = filtered.filter((p) => p.abhaLinked);
  if (filters.includes("last30")) {
    const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
    filtered = filtered.filter((p) => new Date(p.lastSeen).getTime() >= cutoff);
  }
  return filtered;
}

async function fetchAllPatients(search: string, filter: string): Promise<RealPatientsResponse> {
  const response = await apiClient.get("/patients", {
    params: { limit: PAGE_SIZE, offset: 0, search, filter },
  });
  const list = Array.isArray(response.data)
    ? (response.data as RawPatient[])
    : Array.isArray(response.data?.patients)
      ? (response.data.patients as RawPatient[])
      : [];
  return {
    patients: list,
    total: list.length,
    limit: PAGE_SIZE,
    offset: 0,
  };
}

export async function fetchPatientsPageReal(params: {
  offset: number;
  limit: number;
  search: string;
  filters: string[];
}) {
  const selectedFilter = params.filters.includes("all") ? "all" : params.filters[0] || "all";
  const raw = await fetchAllPatients(params.search, selectedFilter);
  const normalized = raw.patients.map(normalizePatient);
  const filtered = applyClientFilters(normalized, params.search, params.filters);
  const total = filtered.length;
  const data = filtered.slice(params.offset, params.offset + params.limit);
  return {
    data,
    total,
    hasMore: params.offset + params.limit < total,
  };
}

export function usePatients(search: string, filters: string[]) {
  return useInfiniteQuery({
    queryKey: ["patients", search, filters.join(",")],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      fetchPatientsPageReal({
        offset: pageParam,
        limit: PAGE_SIZE,
        search,
        filters,
      }),
    getNextPageParam: (lastPage, allPages) => (lastPage.hasMore ? allPages.length * PAGE_SIZE : undefined),
  });
}
