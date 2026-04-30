import Dexie, { type Table } from "dexie";

export type SyncRecordType = "consent" | "vitals" | "clinical_note";

export type SyncRecord = {
  id: string;
  type: SyncRecordType;
  patient_id: string;
  visit_id: string;
  doctor_id: string;
  payload: Record<string, unknown>;
  consent_text_version?: string;
  language?: string;
  patient_confirmed?: boolean;
  timestamp: string;
  synced_at: string | null;
  retry_count: number;
  last_retry_at: string | null;
};

class ClinicOfflineDB extends Dexie {
  sync_records!: Table<SyncRecord, string>;

  constructor() {
    super("clinic_ai_offline_db");
    this.version(1).stores({
      sync_records: "id, type, patient_id, visit_id, doctor_id, synced_at, retry_count, timestamp",
    });
  }
}

export const offlineDB = new ClinicOfflineDB();
