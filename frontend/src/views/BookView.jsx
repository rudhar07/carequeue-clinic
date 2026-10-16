import { useEffect, useState } from "react";
import { api } from "../api";
import PatientForm from "../components/PatientForm";
import SlotGrid from "../components/SlotGrid";
import { LoadState } from "../components/Status";
import { formatPhone, formatSlot, isoDate } from "../lib/format";
import { useToast } from "../lib/toast";
import { useAsync } from "../lib/useAsync";

// Step 1 doctor -> step 2 date + slot -> step 3 patient + reason -> token.
export default function BookView({ onChange }) {
  const toast = useToast();
  const doctors = useAsync(() => api.doctors({ active_only: true }), []);
  const [doctorId, setDoctorId] = useState("");
  const [date, setDate] = useState(isoDate());
  const [slot, setSlot] = useState(null);
  const [patient, setPatient] = useState(null);
  const [reason, setReason] = useState("");
  const [booked, setBooked] = useState(null);
  const [booking, setBooking] = useState(false);

  // Pick the first doctor once the list arrives.
  useEffect(() => {
    if (!doctorId && doctors.data?.length) setDoctorId(String(doctors.data[0].id));
  }, [doctors.data, doctorId]);

  const slots = useAsync(
    () => (doctorId ? api.slots(doctorId, date) : Promise.resolve(null)),
    [doctorId, date],
  );
  useEffect(() => setSlot(null), [doctorId, date]);

  const doctor = doctors.data?.find((d) => String(d.id) === doctorId);

  async function book(e) {
    e.preventDefault();
    setBooking(true);
    try {
      const appt = await api.book({
        doctor_id: Number(doctorId),
        patient_id: patient.id,
        appointment_date: date,
        slot_time: slot,
        reason,
      });
      setBooked(appt);
      setSlot(null);
      setReason("");
      toast(`Token #${appt.token_number} booked for ${appt.patient.full_name}`);
      slots.reload();
      onChange();
    } catch (err) {
      toast(err.message, "error");
      slots.reload();
    } finally {
      setBooking(false);
    }
  }

  return (
    <div className="grid-2">
      <section className="card">
        <h2>
          <span className="step">1</span> Doctor &amp; time
        </h2>
        <LoadState loading={doctors.loading} error={doctors.error} onRetry={doctors.reload} />
        {doctors.data && (
          <>
            <div className="form-row">
              <label>
                Doctor
                <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
                  {doctors.data.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.full_name} - {d.specialty}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Date
                <input type="date" value={date} min={isoDate()} onChange={(e) => setDate(e.target.value)} required />
              </label>
            </div>
            {doctor && (
              <p className="muted">
                Room {doctor.room} &middot; {formatSlot(doctor.start_time)} - {formatSlot(doctor.end_time)} &middot;{" "}
                {doctor.slot_minutes}-minute slots
              </p>
            )}
            <LoadState loading={slots.loading} error={slots.error} onRetry={slots.reload} />
            {slots.data && (
              <>
                <div className="legend">
                  <span className="slot-dot slot-free" /> Free ({slots.data.free_count})
                  <span className="slot-dot slot-booked" /> Booked
                  <span className="slot-dot slot-past" /> Past
                </div>
                <SlotGrid slots={slots.data.slots} selected={slot} onSelect={setSlot} />
              </>
            )}
          </>
        )}
      </section>

      <section className="card">
        <h2>
          <span className="step">2</span> Patient
        </h2>
        <PatientPicker patient={patient} onPick={setPatient} />

        <h2>
          <span className="step">3</span> Confirm
        </h2>
        <form className="form" onSubmit={book}>
          <label>
            Reason for visit
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} rows={2}
              placeholder="e.g. Fever for 3 days" />
          </label>
          <p className="summary">
            {doctor ? doctor.full_name : "No doctor"} &middot; {date} &middot;{" "}
            {slot ? formatSlot(slot) : "pick a slot"} &middot; {patient ? patient.full_name : "pick a patient"}
          </p>
          <button type="submit" className="btn btn-primary btn-block" disabled={!slot || !patient || booking}>
            {booking ? "Booking..." : "Book appointment"}
          </button>
        </form>

        {booked && (
          <div className="token-card" role="status">
            <div className="token-number">#{booked.token_number}</div>
            <div>
              <strong>{booked.patient.full_name}</strong>
              <div className="muted">
                {booked.doctor.full_name} &middot; Room {booked.doctor.room}
                <br />
                {booked.appointment_date} at {formatSlot(booked.slot_time)}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

// Find a patient by phone/name, or register a new one on the spot.
function PatientPicker({ patient, onPick }) {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (q.trim().length < 3) {
      setResults([]);
      return undefined;
    }
    const timer = setTimeout(() => {
      api.patients(q.trim()).then(setResults, (err) => toast(err.message, "error"));
    }, 250);
    return () => clearTimeout(timer);
  }, [q, toast]);

  async function create(form) {
    try {
      const created = await api.createPatient(form);
      toast(`Registered ${created.full_name}`);
      onPick(created);
      setAdding(false);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  if (patient)
    return (
      <div className="picked">
        <div>
          <strong>{patient.full_name}</strong>
          <div className="muted">{formatPhone(patient.phone)}</div>
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => onPick(null)}>
          Change
        </button>
      </div>
    );

  if (adding)
    return <PatientForm initial={{ phone: q }} onSubmit={create} onCancel={() => setAdding(false)} submitLabel="Register patient" />;

  return (
    <div className="form">
      <label>
        Search by mobile number or name
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="98765..." />
      </label>
      {results.length > 0 && (
        <ul className="pick-list">
          {results.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => onPick(p)}>
                <strong>{p.full_name}</strong> <span className="muted">{formatPhone(p.phone)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {q.trim().length >= 3 && results.length === 0 && <p className="muted">No patient found.</p>}
      <button type="button" className="btn btn-ghost" onClick={() => setAdding(true)}>
        + New patient
      </button>
    </div>
  );
}
