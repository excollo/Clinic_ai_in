export type TranscriptionSegment = {
  speaker: "Doctor" | "Patient" | "Attendant";
  timestamp: string;
  text: string;
  confidence: number;
};

export type TranscriptionResult = {
  transcript_id: string;
  segments: TranscriptionSegment[];
  average_confidence: number;
  language_detected: string;
};

export type RxItemRequest = {
  name: string;
  dose: string;
  frequency: string;
  duration: string;
  food_instruction: string;
};

export type InvestigationItemRequest = {
  test: string;
  urgency: "routine" | "urgent" | "stat";
  timing: string;
};

export type IndiaClinicalNoteRequest = {
  visit_id: string;
  patient_id: string;
  transcript_id?: string;
  assessment: string;
  plan: string;
  rx: RxItemRequest[];
  investigations: InvestigationItemRequest[];
  red_flags: string[];
  follow_up: { date?: string; instruction?: string };
  status: "draft" | "approved";
};
