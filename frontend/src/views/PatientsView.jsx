import { useEffect, useState } from "react";
import { api } from "../api";
import PatientForm from "../components/PatientForm";
import { LoadState } from "../components/Status";
import { ageFrom, formatPhone } from "../lib/format";
import { useToast } from "../lib/toast";
import { useAsync } from "../lib/useAsync";

export default function PatientsView({ onChange }) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  // null = list only, {} = adding, {id,...} = editing
  const [editing, setEditing] = useState(null);

  // Debounce typing so we search once the user pauses.
  useEffect(() => {
    const timer = setTimeout(() => setQ(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const patients = useAsync(() => api.patients(q), [q]);

  async function save(form) {
    try {
      if (editing.id) {
        await api.updatePatient(editing.id, form);
        toast(`Updated ${form.full_name}`);
      } else {
        await api.createPatient(form);
        toast(`Registered ${form.full_name}`);
      }
      setEditing(null);
      patients.reload();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function remove(p) {
    if (!window.confirm(`Delete ${p.full_name} and their past visits?`)) return;
    try {
      await api.deletePatient(p.id);
      toast(`Deleted ${p.full_name}`);
      patients.reload();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <div className="grid-2 grid-wide-left">
      <section className="card">
        <div className="card-head">
          <h2>Patients</h2>
          <input
            type="search"
            className="search"
            aria-label="Search patients"
            placeholder="Search name or mobile"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <LoadState loading={patients.loading} error={patients.error} onRetry={patients.reload} />
        {patients.data && patients.data.length === 0 && <p className="muted">No patients match.</p>}
        {patients.data && patients.data.length > 0 && (
          <ul className="people">
            {patients.data.map((p) => (
              <li key={p.id} className="person">
                <div className={`avatar avatar-${p.gender}`} aria-hidden="true">
                  {p.full_name.charAt(0)}
                </div>
                <div className="person-main">
                  <strong>{p.full_name}</strong>
                  <span className="muted">
                    {formatPhone(p.phone)} &middot; {ageFrom(p.date_of_birth)} y &middot; {p.gender}
                  </span>
                </div>
                <div className="person-actions">
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(p)}>
                    Edit
                  </button>
                  <button type="button" className="btn btn-sm btn-ghost btn-danger" onClick={() => remove(p)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        {editing ? (
          <>
            <h2>{editing.id ? `Edit ${editing.full_name}` : "New patient"}</h2>
            <PatientForm key={editing.id || "new"} initial={editing} onSubmit={save} onCancel={() => setEditing(null)} />
          </>
        ) : (
          <>
            <h2>Register a patient</h2>
            <p className="muted">Mobile numbers are unique: one record per patient.</p>
            <button type="button" className="btn btn-primary" onClick={() => setEditing({})}>
              + Add patient
            </button>
          </>
        )}
      </section>
    </div>
  );
}
