import { useState } from "react";
import { api } from "../api";
import DoctorForm from "../components/DoctorForm";
import { LoadState } from "../components/Status";
import { formatSlot } from "../lib/format";
import { useToast } from "../lib/toast";
import { useAsync } from "../lib/useAsync";

export default function DoctorsView({ onChange }) {
  const toast = useToast();
  const doctors = useAsync(() => api.doctors(), []);
  const [editing, setEditing] = useState(null); // null | {} (new) | doctor

  async function save(form) {
    try {
      if (editing.id) {
        await api.updateDoctor(editing.id, form);
        toast(`Updated ${form.full_name}`);
      } else {
        await api.createDoctor(form);
        toast(`Added ${form.full_name}`);
      }
      setEditing(null);
      doctors.reload();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function setActive(d, active) {
    try {
      if (active) {
        await api.updateDoctor(d.id, { ...d, is_active: true });
        toast(`${d.full_name} is taking appointments again`);
      } else {
        if (!window.confirm(`Deactivate ${d.full_name}? Existing appointments are kept.`)) return;
        const result = await api.deleteDoctor(d.id);
        toast(result.action === "deleted" ? `Removed ${d.full_name}` : `Deactivated ${d.full_name}`);
      }
      doctors.reload();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <div className="doctors">
      <div className="card-head">
        <h2>Doctors</h2>
        <button type="button" className="btn btn-primary" onClick={() => setEditing({})}>
          + Add doctor
        </button>
      </div>

      {editing && (
        <section className="card">
          <h2>{editing.id ? `Edit ${editing.full_name}` : "New doctor"}</h2>
          <DoctorForm key={editing.id || "new"} initial={editing} onSubmit={save} onCancel={() => setEditing(null)} />
        </section>
      )}

      <LoadState loading={doctors.loading} error={doctors.error} onRetry={doctors.reload} />
      {doctors.data && (
        <div className="doctor-grid">
          {doctors.data.map((d) => (
            <article key={d.id} className={`card doctor${d.is_active ? "" : " doctor-inactive"}`}>
              <p className="eyebrow">{d.specialty}</p>
              <h3>{d.full_name}</h3>
              <p className="muted">
                Room {d.room} &middot; {formatSlot(d.start_time)} - {formatSlot(d.end_time)}
                <br />
                {d.slot_minutes}-minute slots {d.is_active ? "" : "· inactive"}
              </p>
              <div className="person-actions">
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(d)}>
                  Edit
                </button>
                {d.is_active ? (
                  <button type="button" className="btn btn-sm btn-ghost btn-danger" onClick={() => setActive(d, false)}>
                    Deactivate
                  </button>
                ) : (
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => setActive(d, true)}>
                    Reactivate
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
