export type CalendarAppointment = {
  id: string;
  visitId: string;
  patientName: string;
  visitType: "scheduled" | "follow-up" | "chronic care";
  start: string;
  end: string;
};

const base = new Date();
base.setHours(9, 0, 0, 0);

const make = (dayOffset: number, hour: number, minute: number, patientName: string, visitType: CalendarAppointment["visitType"], id: string): CalendarAppointment => {
  const start = new Date(base);
  start.setDate(base.getDate() + dayOffset);
  start.setHours(hour, minute, 0, 0);
  const end = new Date(start);
  end.setMinutes(end.getMinutes() + 20);
  return { id, visitId: `vis_cal_${id}`, patientName, visitType, start: start.toISOString(), end: end.toISOString() };
};

export const weeklyAppointments: CalendarAppointment[] = [
  make(0, 9, 0, "ravi patel", "scheduled", "01"),
  make(0, 11, 30, "meera verma", "follow-up", "02"),
  make(1, 10, 0, "suresh gupta", "chronic care", "03"),
  make(1, 14, 15, "nisha iyer", "scheduled", "04"),
  make(2, 9, 45, "aman singh", "scheduled", "05"),
  make(2, 16, 0, "priyanka das", "follow-up", "06"),
  make(3, 10, 30, "farhan khan", "chronic care", "07"),
  make(3, 12, 15, "rekha nair", "scheduled", "08"),
  make(4, 11, 0, "rohit jain", "scheduled", "09"),
  make(4, 15, 30, "anita paul", "follow-up", "10"),
  make(5, 9, 30, "mohit rao", "scheduled", "11"),
  make(6, 13, 0, "sana ali", "chronic care", "12"),
];
