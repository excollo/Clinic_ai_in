export type LabResult = {
  id: string;
  patientName: string;
  reportType: string;
  source: "whatsapp" | "uploaded";
  receivedAt: string;
  abnormal: boolean;
  reviewed: boolean;
  pendingReview: boolean;
  lowConfidence: boolean;
  fileType: "pdf" | "image";
  values: Array<{ test: string; value: string; unit: string; refRange: string; status: "normal" | "abnormal" }>;
};

const now = Date.now();
export const mockLabs: LabResult[] = [
  {
    id: "lab_001",
    patientName: "ravi patel",
    reportType: "blood panel",
    source: "whatsapp",
    receivedAt: new Date(now - 60 * 60 * 1000).toISOString(),
    abnormal: true,
    reviewed: false,
    pendingReview: true,
    lowConfidence: false,
    fileType: "pdf",
    values: [
      { test: "HbA1c", value: "8.4", unit: "%", refRange: "4.0-5.6", status: "abnormal" },
      { test: "LDL", value: "172", unit: "mg/dL", refRange: "<100", status: "abnormal" },
      { test: "HDL", value: "45", unit: "mg/dL", refRange: ">40", status: "normal" },
    ],
  },
  {
    id: "lab_002",
    patientName: "meera verma",
    reportType: "urine routine",
    source: "uploaded",
    receivedAt: new Date(now - 3 * 60 * 60 * 1000).toISOString(),
    abnormal: false,
    reviewed: true,
    pendingReview: false,
    lowConfidence: false,
    fileType: "image",
    values: [{ test: "protein", value: "negative", unit: "-", refRange: "negative", status: "normal" }],
  },
  {
    id: "lab_003",
    patientName: "suresh gupta",
    reportType: "thyroid panel",
    source: "whatsapp",
    receivedAt: new Date(now - 5 * 60 * 60 * 1000).toISOString(),
    abnormal: false,
    reviewed: false,
    pendingReview: true,
    lowConfidence: true,
    fileType: "pdf",
    values: [{ test: "TSH", value: "4.9", unit: "uIU/mL", refRange: "0.4-4.5", status: "abnormal" }],
  },
];

export function getLabById(labId: string) {
  return mockLabs.find((lab) => lab.id === labId) ?? mockLabs[0];
}
