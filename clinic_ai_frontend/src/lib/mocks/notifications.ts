export type AppNotification = {
  id: string;
  type: "lab_ready" | "follow_up_due" | "whatsapp_failed" | "consent_pending_sync" | "appointment_booked";
  title: string;
  description: string;
  createdAt: string;
  target: string;
  read: boolean;
};

const now = Date.now();
const mk = (id: string, hoursAgo: number, type: AppNotification["type"], title: string, description: string, target: string): AppNotification => ({
  id,
  type,
  title,
  description,
  target,
  createdAt: new Date(now - hoursAgo * 60 * 60 * 1000).toISOString(),
  read: false,
});

export const mockNotifications: AppNotification[] = [
  mk("n1", 1, "lab_ready", "lab ready", "ravi patel blood panel is ready", "/lab-inbox/lab_001"),
  mk("n2", 2, "lab_ready", "lab ready", "meera verma urine routine uploaded", "/lab-inbox/lab_002"),
  mk("n3", 3, "lab_ready", "lab ready", "suresh gupta thyroid panel parsed", "/lab-inbox/lab_003"),
  mk("n4", 18, "lab_ready", "lab ready", "anita paul cbc available", "/lab-inbox"),
  mk("n5", 5, "follow_up_due", "Follow-up due", "Nisha Iyer follow-up due today", "/patients"),
  mk("n6", 28, "follow_up_due", "Follow-up due", "Rohit Jain follow-up overdue", "/patients"),
  mk("n7", 46, "follow_up_due", "Follow-up due", "Farhan Khan due in 24h", "/patients"),
  mk("n8", 4, "whatsapp_failed", "whatsapp failed", "recap failed for opd-13", "/visits/vis_chest_001/recap-sent"),
  mk("n9", 30, "whatsapp_failed", "whatsapp failed", "reminder failed for opd-15", "/calendar"),
  mk("n10", 70, "whatsapp_failed", "whatsapp failed", "lab summary send failed", "/lab-inbox/lab_001"),
];
