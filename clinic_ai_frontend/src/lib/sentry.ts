export async function initSentry() {
  if (!import.meta.env.VITE_SENTRY_DSN) return;
  const Sentry = await import("@sentry/react");
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [],
    tracesSampleRate: 0,
  });
}
