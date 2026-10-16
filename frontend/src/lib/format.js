// Small display helpers shared by the views.

/** "14:30:00" -> "2:30 PM" */
export function formatSlot(time) {
  const [h, m] = time.split(":").map(Number);
  const suffix = h >= 12 ? "PM" : "AM";
  const hour = h % 12 === 0 ? 12 : h % 12;
  return `${hour}:${String(m).padStart(2, "0")} ${suffix}`;
}

/** Local calendar date as YYYY-MM-DD (not UTC, which can be a day off in India). */
export function isoDate(d = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Age in whole years on `today`. */
export function ageFrom(dob, today = new Date()) {
  const birth = new Date(`${dob}T00:00:00`);
  let age = today.getFullYear() - birth.getFullYear();
  const beforeBirthday =
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

/** "9876543210" -> "98765 43210" */
export function formatPhone(phone) {
  return phone.length === 10 ? `${phone.slice(0, 5)} ${phone.slice(5)}` : phone;
}

export const STATUS_LABELS = {
  booked: "Booked",
  checked_in: "Waiting",
  in_consultation: "In consultation",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No-show",
};
