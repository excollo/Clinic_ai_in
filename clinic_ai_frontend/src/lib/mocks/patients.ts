export type PatientRecord = {
  id: string;
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

const firstNames = ["aarav", "vihaan", "isha", "meera", "ravi", "sana", "kabir", "rohit", "ananya", "priya"];
const lastNames = ["sharma", "patel", "verma", "khan", "iyer", "singh", "das", "nair", "gupta", "roy"];
const sexes: Array<PatientRecord["sex"]> = ["male", "female", "other"];

export const mockPatients: PatientRecord[] = Array.from({ length: 100 }, (_, i) => {
  const first = firstNames[i % firstNames.length];
  const last = lastNames[(i * 3) % lastNames.length];
  const age = 18 + (i % 62);
  return {
    id: `pat_${(1000 + i).toString(36)}`,
    name: `${first} ${last}`,
    age,
    sex: sexes[i % 3],
    mobile: `9${(870000000 + i).toString().slice(0, 9)}`,
    visitCount: (i % 12) + 1,
    lastSeen: new Date(Date.now() - i * 86400000).toISOString(),
    chronic: i % 4 === 0,
    abhaLinked: i % 3 === 0,
    language: i % 2 === 0 ? "hindi" : "english",
  };
});

export async function fetchPatientsPage(params: { offset: number; limit: number; search: string; filters: string[] }) {
  const delay = 300 + Math.floor(Math.random() * 200);
  await new Promise((resolve) => setTimeout(resolve, delay));
  let filtered = mockPatients;
  if (params.search.trim()) {
    const q = params.search.toLowerCase();
    filtered = filtered.filter((p) => p.name.toLowerCase().includes(q) || p.mobile.includes(q));
  }
  if (params.filters.includes("chronic")) filtered = filtered.filter((p) => p.chronic);
  if (params.filters.includes("abha")) filtered = filtered.filter((p) => p.abhaLinked);
  if (params.filters.includes("last30")) {
    const threshold = Date.now() - 30 * 86400000;
    filtered = filtered.filter((p) => new Date(p.lastSeen).getTime() >= threshold);
  }
  const total = filtered.length;
  const data = filtered.slice(params.offset, params.offset + params.limit);
  return { data, total, hasMore: params.offset + params.limit < total };
}
