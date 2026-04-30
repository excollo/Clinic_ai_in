import apiClient from "@/lib/apiClient";
import { offlineDB, type SyncRecord, type SyncRecordType } from "./db";

const backoffSeconds = [1, 2, 4, 8, 30];
const FIVE_MIN_MS = 5 * 60 * 1000;
let syncTimer: number | undefined;
let workerRunning = false;
let focusHandler: (() => void) | undefined;
const consentAttemptKey = "consent_sync_mock_attempt";

function nextDelayMs(retryCount: number): number {
  const seconds = backoffSeconds[retryCount] ?? 300;
  return seconds * 1000;
}

function notifyOfflineSyncUpdated() {
  console.info("[OFFLINE_SYNC] event dispatch: offline-sync-updated");
  window.dispatchEvent(new CustomEvent("offline-sync-updated"));
}

async function postRecord(record: SyncRecord): Promise<void> {
  const mockConsentSequence = import.meta.env.VITE_CONSENT_SYNC_TEST_MODE === "true";
  if (record.type === "consent") {
    if (mockConsentSequence) {
      const current = Number(localStorage.getItem(consentAttemptKey) ?? "0") + 1;
      localStorage.setItem(consentAttemptKey, String(current));
      if (current <= 3) {
        console.warn(`[CONSENT_SYNC] mock failure attempt ${current} for ${record.id}`);
        throw new Error("mock consent sync failure");
      }
      console.info(`[CONSENT_SYNC] mock success attempt ${current} for ${record.id}`);
      return;
    }
    await apiClient.post("/consent/capture", record.payload, {
      headers: { "X-Idempotency-Key": record.id },
    });
  } else if (record.type === "vitals") {
    await apiClient.post(`/patients/${record.patient_id}/visits/${record.visit_id}/vitals`, record.payload);
  } else {
    await apiClient.post("/notes/india-clinical-note", record.payload);
  }
}

export async function enqueueSyncRecord(input: Omit<SyncRecord, "synced_at" | "retry_count" | "last_retry_at">) {
  await offlineDB.sync_records.put({
    ...input,
    synced_at: null,
    retry_count: 0,
    last_retry_at: null,
  });
  notifyOfflineSyncUpdated();
}

export async function getUnsyncedCount(): Promise<number> {
  const all = await offlineDB.sync_records.toArray();
  return all.filter((record) => record.synced_at === null).length;
}

export async function cleanupSyncedRecords() {
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const all = await offlineDB.sync_records.toArray();
  const synced = all.filter((record) => record.synced_at !== null);
  await Promise.all(
    synced
      .filter((record) => record.synced_at && new Date(record.synced_at).getTime() < cutoff)
      .map((record) => offlineDB.sync_records.delete(record.id)),
  );
}

export async function runSyncNow() {
  const all = await offlineDB.sync_records.toArray();
  const pending = all.filter((record) => record.synced_at === null);
  for (const record of pending) {
    try {
      await postRecord(record);
      await offlineDB.sync_records.update(record.id, { synced_at: new Date().toISOString() });
      console.info(`[OFFLINE_SYNC] Synced record ${record.id}`);
      notifyOfflineSyncUpdated();
    } catch {
      await offlineDB.sync_records.update(record.id, {
        retry_count: record.retry_count + 1,
        last_retry_at: new Date().toISOString(),
      });
      console.warn("offline sync retry queued for record", record.id);
      notifyOfflineSyncUpdated();
    }
  }
}

export function startOfflineSyncWorker() {
  if (workerRunning) return;
  workerRunning = true;
  void cleanupSyncedRecords();
  const tick = async () => {
    await runSyncNow();
    const all = await offlineDB.sync_records.toArray();
    const pending = all.filter((record) => record.synced_at === null);
    const maxRetry = pending.reduce((max, item) => Math.max(max, item.retry_count), 0);
    const waitMs = pending.length === 0 ? FIVE_MIN_MS : nextDelayMs(maxRetry);
    syncTimer = window.setTimeout(() => void tick(), waitMs);
  };
  void tick();
  focusHandler = () => {
    void runSyncNow();
  };
  window.addEventListener("focus", focusHandler);
}

export function stopOfflineSyncWorker() {
  workerRunning = false;
  if (syncTimer) {
    window.clearTimeout(syncTimer);
  }
  if (focusHandler) {
    window.removeEventListener("focus", focusHandler);
  }
}

export async function queueClinicalRecord(
  type: SyncRecordType,
  data: {
    id: string;
    patient_id: string;
    visit_id: string;
    doctor_id: string;
    payload: Record<string, unknown>;
    consent_text_version?: string;
    language?: string;
    patient_confirmed?: boolean;
  },
) {
  await enqueueSyncRecord({
    ...data,
    type,
    timestamp: new Date().toISOString(),
  });
}
