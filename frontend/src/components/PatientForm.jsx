import { useState } from "react";

const EMPTY = { full_name: "", phone: "", date_of_birth: "", gender: "female" };

// Add / edit a patient. The backend does the real validation (Indian mobile,
// unique phone, date of birth); the browser checks catch obvious typos early.
export default function PatientForm({ initial, onSubmit, onCancel, submitLabel = "Save patient" }) {
  const [form, setForm] = useState({ ...EMPTY, ...initial });
  const [saving, setSaving] = useState(false);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit(form);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label>
        Full name
        <input value={form.full_name} onChange={set("full_name")} required minLength={2} maxLength={120} />
      </label>
      <label>
        Mobile number
        <input
          value={form.phone}
          onChange={set("phone")}
          required
          inputMode="tel"
          placeholder="98765 43210"
          pattern="\+?[0-9 ]{10,15}"
          title="10-digit Indian mobile number"
        />
      </label>
      <div className="form-row">
        <label>
          Date of birth
          <input type="date" value={form.date_of_birth} onChange={set("date_of_birth")} required />
        </label>
        <label>
          Gender
          <select value={form.gender} onChange={set("gender")}>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
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
          {saving ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
