export type CarePrepItem = {
  visitId: string;
  token: string;
  patientName: string;
  age: number;
  sex: string;
  chiefComplaint: string;
  questionCount: number;
  imageCount: number;
  reviewed: boolean;
  visitType: "walk_in" | "scheduled";
  hasRedFlag: boolean;
  redFlags: string[];
  language: string;
  registeredAt: string;
};

const now = Date.now();
export const careprepQueue: CarePrepItem[] = [
  { visitId: "vis_chest_001", token: "OPD-13", patientName: "ravi patel", age: 54, sex: "male", chiefComplaint: "chest pain and breathlessness", questionCount: 12, imageCount: 2, reviewed: false, visitType: "walk_in", hasRedFlag: true, redFlags: ["exertional chest pain", "breathlessness"], language: "hindi", registeredAt: new Date(now - 35 * 60 * 1000).toISOString() },
  { visitId: "vis_fever_001", token: "OPD-14", patientName: "meera verma", age: 32, sex: "female", chiefComplaint: "fever with body ache", questionCount: 9, imageCount: 0, reviewed: false, visitType: "scheduled", hasRedFlag: false, redFlags: [], language: "english", registeredAt: new Date(now - 60 * 60 * 1000).toISOString() },
  { visitId: "vis_back_001", token: "OPD-15", patientName: "suresh gupta", age: 46, sex: "male", chiefComplaint: "back pain for 2 weeks", questionCount: 10, imageCount: 1, reviewed: true, visitType: "walk_in", hasRedFlag: false, redFlags: [], language: "hindi", registeredAt: new Date(now - 95 * 60 * 1000).toISOString() },
  { visitId: "vis_004", token: "OPD-16", patientName: "nisha iyer", age: 40, sex: "female", chiefComplaint: "palpitations and dizziness", questionCount: 8, imageCount: 1, reviewed: false, visitType: "scheduled", hasRedFlag: true, redFlags: ["palpitations with dizziness"], language: "english", registeredAt: new Date(now - 120 * 60 * 1000).toISOString() },
  { visitId: "vis_005", token: "OPD-17", patientName: "aman singh", age: 28, sex: "male", chiefComplaint: "persistent cough", questionCount: 7, imageCount: 0, reviewed: true, visitType: "scheduled", hasRedFlag: false, redFlags: [], language: "hindi", registeredAt: new Date(now - 150 * 60 * 1000).toISOString() },
  { visitId: "vis_006", token: "OPD-18", patientName: "priyanka das", age: 36, sex: "female", chiefComplaint: "migraine episodes", questionCount: 11, imageCount: 0, reviewed: false, visitType: "walk_in", hasRedFlag: false, redFlags: [], language: "english", registeredAt: new Date(now - 190 * 60 * 1000).toISOString() },
  { visitId: "vis_007", token: "OPD-19", patientName: "farhan khan", age: 50, sex: "male", chiefComplaint: "uncontrolled diabetes review", questionCount: 6, imageCount: 0, reviewed: true, visitType: "scheduled", hasRedFlag: false, redFlags: [], language: "hindi", registeredAt: new Date(now - 220 * 60 * 1000).toISOString() },
  { visitId: "vis_008", token: "OPD-20", patientName: "rekha nair", age: 61, sex: "female", chiefComplaint: "leg swelling", questionCount: 9, imageCount: 2, reviewed: false, visitType: "walk_in", hasRedFlag: false, redFlags: [], language: "english", registeredAt: new Date(now - 260 * 60 * 1000).toISOString() },
];

export async function fetchCareprepQueue(): Promise<CarePrepItem[]> {
  await new Promise((r) => setTimeout(r, 350));
  return [...careprepQueue];
}

export function getCareprepByVisitId(visitId: string) {
  return careprepQueue.find((item) => item.visitId === visitId) ?? careprepQueue[0];
}
