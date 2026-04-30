export type MockVisit = {
  visitId: string;
  patientId: string;
  patientName: string;
  patientAge: number;
  patientSex: "male" | "female" | "other";
  tokenNumber: string;
  visitType: "walk_in" | "scheduled";
  status: "in_consult" | "done";
  chiefComplaint: string;
  patientLanguage: string;
};

export const mockVisits: MockVisit[] = [
  {
    visitId: "vis_chest_001",
    patientId: "pat_chest_001",
    patientName: "ravi patel",
    patientAge: 54,
    patientSex: "male",
    tokenNumber: "OPD-13",
    visitType: "walk_in",
    status: "in_consult",
    chiefComplaint: "chest pain and breathless",
    patientLanguage: "hindi",
  },
  {
    visitId: "vis_fever_001",
    patientId: "pat_fever_001",
    patientName: "meera verma",
    patientAge: 32,
    patientSex: "female",
    tokenNumber: "OPD-14",
    visitType: "scheduled",
    status: "in_consult",
    chiefComplaint: "fever with body ache",
    patientLanguage: "english",
  },
  {
    visitId: "vis_back_001",
    patientId: "pat_back_001",
    patientName: "suresh gupta",
    patientAge: 46,
    patientSex: "male",
    tokenNumber: "OPD-15",
    visitType: "walk_in",
    status: "in_consult",
    chiefComplaint: "back pain for 2 weeks",
    patientLanguage: "hindi",
  },
];

export function getMockVisitById(visitId: string) {
  return mockVisits.find((v) => v.visitId === visitId) ?? mockVisits[0];
}
