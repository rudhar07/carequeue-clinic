import { useState } from "react";

const EMPTY = {
  full_name: "",
  specialty: "General Medicine",
  room: "",
  slot_minutes: 15,
  start_time: "09:00",
  end_time: "17:00",
  is_active: true,
};

export const SPECIALTIES = [
  "General Medicine",
  "Pediatrics",
  "Dermatology",
  "Orthopedics",
  "Gynecology",
  "Cardiology",
  "ENT",
  "Ophthalmology",
];

export default function DoctorForm({ initial, onSubmit, onCancel }) {
  const [form, setForm] = useState(() => {
    const merged = { ...EMPTY, ...initial };
    // API times are "HH:MM:SS"; <input type="time"> wants "HH:MM".
    return { ...merged, start_time: merged.start_time.slice(0, 5), end_time: merged.end_time.slice(0, 5) };
  });
  const [saving, setSaving] = useState(false);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({ ...form, slot_minutes: Number(form.slot_minutes) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label>
        Full name
        <input value={form.full_name} onChange={set("full_name")} required minLength={3} placeholder="Dr. ..." />
      </label>
      <div className="form-row">
        <label>
          Specialty
          <select value={form.specialty} onChange={set("specialty")}>
            {[...new Set([...SPECIALTIES, form.specialty])].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Room
          <input value={form.room} onChange={set("room")} required maxLength={20} />
        </label>
      </div>
      <div className="form-row form-row-3">
        <label>
          Starts
          <input type="time" value={form.start_time} onChange={set("start_time")} required />
        </label>
        <label>
          Ends
          <input type="time" value={form.end_time} onChange={set("end_time")} required />
        </label>
        <label>
          Slot (min)
          <select value={form.slot_minutes} onChange={set("slot_minutes")}>
            {[10, 15, 20, 30, 45, 60].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Saving..." : "Save doctor"}
        </button>
      </div>
    </form>
  );
}
