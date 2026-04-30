type Field = {
  key: string;
  label: string;
  type: "number" | "bp_pair";
  unit: string;
  normal_range: [number, number] | { systolic: [number, number]; diastolic: [number, number] } | null;
  ai_reason?: string;
};

type ResponseShape = {
  fixed_fields: Field[];
  dynamic_fields: Field[];
  complaint_processed: string;
};

const fixedFields: Field[] = [
  {
    key: "blood_pressure",
    label: "blood pressure",
    type: "bp_pair",
    unit: "mmHg",
    normal_range: { systolic: [90, 130], diastolic: [60, 85] },
  },
  {
    key: "weight",
    label: "weight",
    type: "number",
    unit: "kg",
    normal_range: null,
  },
];

const templates: Record<string, Field[]> = {
  "chest pain": [
    { key: "pulse", label: "Pulse", type: "number", unit: "bpm", normal_range: [60, 100], ai_reason: "Suggested for cardiac complaint" },
    { key: "spo2", label: "SpO₂", type: "number", unit: "%", normal_range: [95, 100], ai_reason: "Suggested for cardiac complaint" },
    { key: "temperature", label: "Temperature", type: "number", unit: "°F", normal_range: [97, 99.5], ai_reason: "Suggested for cardiac complaint" },
    { key: "respiratory_rate", label: "Resp. rate", type: "number", unit: "breaths/min", normal_range: [12, 20], ai_reason: "Suggested for cardiac complaint" },
  ],
  fever: [
    { key: "temperature", label: "Temperature", type: "number", unit: "°F", normal_range: [97, 99.5], ai_reason: "Suggested for fever complaint" },
    { key: "pulse", label: "Pulse", type: "number", unit: "bpm", normal_range: [60, 100], ai_reason: "Suggested for fever complaint" },
  ],
  diabetes: [
    { key: "pulse", label: "Pulse", type: "number", unit: "bpm", normal_range: [60, 100], ai_reason: "Suggested for diabetes complaint" },
    { key: "blood_glucose", label: "Blood glucose", type: "number", unit: "mg/dL", normal_range: [70, 140], ai_reason: "Suggested for diabetes complaint" },
  ],
  "back pain": [],
  default: [
    { key: "pulse", label: "Pulse", type: "number", unit: "bpm", normal_range: [60, 100], ai_reason: "Suggested based on complaint" },
    { key: "temperature", label: "Temperature", type: "number", unit: "°F", normal_range: [97, 99.5], ai_reason: "Suggested based on complaint" },
  ],
};

export async function getMockVitalsRequiredFields(complaint: string): Promise<ResponseShape> {
  const lowered = complaint.toLowerCase();
  const delay = 400 + Math.floor(Math.random() * 400);
  await new Promise((resolve) => setTimeout(resolve, delay));

  const dynamic: Field[] = templates[lowered] ?? templates.default;

  return {
    fixed_fields: fixedFields,
    dynamic_fields: dynamic,
    complaint_processed: lowered || "general",
  };
}
