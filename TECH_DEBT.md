## Bundle Optimization Deferred
- **Description:** `react-vendor` and offline sync chunks are large (`54.01 kB` and `33.48 kB` gzipped respectively), and route chunks are not grouped by user journey budget.
- **Reason for deferring:** Delivery focus prioritized end-to-end flows over fine-grained chunk strategy.
- **Estimated effort:** 1-2 days.
- **Trigger to revisit:** When total gzipped JS exceeds 200 kB on critical routes or Lighthouse performance drops below 90.

## Backend Integration Mocked
- **Description:** Multiple frontend surfaces rely on in-app mock data or mock fallback paths (careprep, lab inbox/detail, notifications, settings save, ABHA lookup fallback, consent text fallback).
- **Reason for deferring:** Backend contract stabilization happened in parallel; UI scaffolds were built first.
- **Estimated effort:** 3-5 days.
- **Trigger to revisit:** Before pilot clinics or when API readiness reaches >=90% of required endpoints.

## UX Refinements Deferred
- **Description:** Several actions show placeholders/toasts without true persistence (e.g., schedule activation, family-recipient handling details, some confirmation states).
- **Reason for deferring:** Focus was on critical happy-path navigation first.
- **Estimated effort:** 2-4 days.
- **Trigger to revisit:** Before external user rollout.

## Edge Cases Not Handled
- **Description:** Flow-level fallback gaps exist (e.g., login has no mock fallback unlike other auth paths, forgotten-password reset route mismatch, conditional flows without explicit error recovery).
- **Reason for deferring:** Time-boxed implementation for core paths.
- **Estimated effort:** 2-3 days.
- **Trigger to revisit:** Before internal testing with non-engineering users.

## Testing Coverage Gaps
- **Description:** Frontend has minimal E2E specs and no meaningful unit/integration coverage for key journeys; backend integration has a failing forgot-password test path.
- **Reason for deferring:** Product iteration outpaced test authoring.
- **Estimated effort:** 4-6 days.
- **Trigger to revisit:** Mandatory before pilot clinics.

## Accessibility Issues
- **Description:** Lighthouse accessibility is good overall, but interactive custom components and virtualized lists need focused keyboard and SR regression checks.
- **Reason for deferring:** Accessibility was handled opportunistically, not as a dedicated test stream.
- **Estimated effort:** 1-2 days.
- **Trigger to revisit:** Before launch readiness review.

## Performance Issues
- **Description:** First Contentful Paint (`2.2s`) and Largest Contentful Paint (`2.6s`) are acceptable but can regress under slower clinic networks; forced reflow/network dependency insights are flagged by Lighthouse.
- **Reason for deferring:** Initial optimization targeted functional correctness first.
- **Estimated effort:** 1-3 days.
- **Trigger to revisit:** If dashboard Lighthouse performance <90 or route TTI >3s on cold cache.

## Security Considerations Deferred
- **Description:** Consent and critical write APIs have partial offline/idempotency handling, but no visible consent withdrawal UX and uneven endpoint hardening in UI flows.
- **Reason for deferring:** Compliance-adjacent features were staged behind baseline functionality.
- **Estimated effort:** 2-4 days.
- **Trigger to revisit:** Before handling real patient data in production environments.

## Test Suite Status Note
- **Description:** Repo has at least one failing backend integration test (`forgot-password` flow expected `200`, observed `404`).
- **Reason for deferring:** Issue surfaced during audit run and requires endpoint contract alignment.
- **Estimated effort:** 0.5-1 day.
- **Trigger to revisit:** Immediate blocker for release candidate cut.

## Transcription: Local Filesystem Fallback on Missing GridFS

- **Description:** When the Mongo driver is not a real PyMongo ``Database`` (tests or misconfiguration), ``TranscriptionAudioStore`` persists uploads under ``LOCAL_AUDIO_STORAGE_PATH`` with ``path.write_bytes(...)``. Worker FFmpeg paths also write **temporary** WAV under ``tempfile``. Ephemeral-disk paths are **lost on Render redeploy** and are inappropriate for canonical patient audio; production must use MongoDB GridFS.
- **Reason for deferring:** Early-stage deployments optimize for Mongo-only storage; adapter pattern permits Azure Blob later if scale or lifecycle management requires it.
- **Estimated effort:** Already mitigated once ``MONGODB_URL`` resolves to Atlas with GridFS; no blob migration work is scheduled for the current pilot scope.
- **Trigger to revisit:** Before pilot: confirm Render env yields GridFS uploads only (inspect ``storage_ref`` prefix ``gridfs://``). Consider Azure Blob if monthly audio volume or compliance drives dedicated object lifecycle tooling.

## Transcription / Azure Speech: Self-Hosted Signed URL + Render Idle Sleep

- **Description:** Batch transcription obtains audio via ``GET /internal/audio/{audio_id}?token=...`` backed by GridFS (see ``PUBLIC_BACKEND_URL``, ``AUDIO_URL_SIGNING_SECRET``). Azure pull requests hit the Render **web** service during the transcription job window. Render **free** web services idle-sleep after inactivity; Azure could attempt a delayed fetch while the origin is unreachable.
- **Reason for deferring:** Operational choice (tiering) independent of Chunk 2 code.
- **Mitigations:** Paid Render web tier (recommended for production pilot), orchestrated keep-alive to the API while jobs remain processing, or shortening batch queue delay at Azure Speech.
- **Trigger to revisit:** Before production transcription cutover on batch mode.

## Azure Queue Adapter: Implemented, Not Wired to Production Pilot

- **Description:** Sprint 2B Chunk 1 shipped an Azure Storage Queue-backed ``TRANSCRIPTION_QUEUE_BACKEND=azure`` adapter (plus optional Azurite tests). Operational scope was reduced so the pilot relies on Mongo FIFO (~``TRANSCRIPTION_QUEUE_BACKEND=mongo`` default) alongside GridFS-only audio hosting.
- **Reason for deferring:** Cost and simplicity; no production path should load the Azure Queue adapter until scale or Mongo queue depth forces the issue.
- **Estimated effort:** None to keep dormant; flipping env suffices when warranted.
- **Trigger to revisit:** When transcription volume repeatedly exceeds Mongo queue ergonomics (~tens/hundreds of queued jobs sustained, or observable Mongo contention on dequeue), run Azurite or staging integration tests again and flip ``TRANSCRIPTION_QUEUE_BACKEND=azure`` after validation.

## Post-Visit Summary Test Drift
- **Description:** Integration tests patch `send_post_visit_summary_whatsapp` in `generate_post_visit_summary`, but the symbol is no longer exported at that target path, causing monkeypatch `AttributeError`.
- **Reason for deferring:** Not pilot-critical for current Sprint 2A exit; tracked during triage as historical implementation drift.
- **Estimated effort:** 0.5 day.
- **Trigger to revisit:** Sprint 2C while normalizing post-visit summary + WhatsApp delivery contracts.
