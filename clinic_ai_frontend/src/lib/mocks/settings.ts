export async function patchSettingsMock(_tab: string, _payload: Record<string, unknown>) {
  await new Promise((resolve) => setTimeout(resolve, 400));
  return { ok: true };
}

export const auditEntries = Array.from({ length: 15 }).map((_, i) => ({
  id: `audit_${i + 1}`,
  date: new Date(Date.now() - i * 2 * 60 * 60 * 1000).toISOString(),
  actionType: i % 2 === 0 ? "update note" : "send whatsapp",
  patient: i % 2 === 0 ? "ravi patel" : "meera verma",
  user: "Dr. Priya Sharma",
  ip: `10.0.0.${10 + i}`,
}));
