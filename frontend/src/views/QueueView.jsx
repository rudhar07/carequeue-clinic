import { useEffect, useState } from "react";
import { api } from "../api";
import { LoadState, StatusBadge } from "../components/Status";
import { formatSlot } from "../lib/format";
import { useToast } from "../lib/toast";
import { useAsync } from "../lib/useAsync";

const REFRESH_MS = 5000;

// What each button does to an appointment, and its success message.
const ACTIONS = {
  checked_in: { label: "Check-in", done: "checked in", style: "btn-primary" },
  in_consultation: { label: "Call in", done: "called in", style: "btn-primary" },
  completed: { label: "Complete", done: "completed", style: "btn-success" },
  no_show: { label: "No-show", done: "marked no-show", style: "btn-ghost" },
  cancelled: { label: "Cancel", done: "cancelled", style: "btn-ghost btn-danger" },
};

export default function QueueView({ onChange }) {
  const toast = useToast();
  const doctors = useAsync(() => api.doctors({ active_only: true }), []);
  const [doctorId, setDoctorId] = useState(null);

  useEffect(() => {
    if (!doctorId && doctors.data?.length) setDoctorId(doctors.data[0].id);
  }, [doctors.data, doctorId]);

  const queue = useAsync(() => (doctorId ? api.queue(doctorId) : Promise.resolve(null)), [doctorId]);
  const { reload } = queue;

  // Live view: poll every 5 s while the tab is open.
  useEffect(() => {
    const timer = setInterval(reload, REFRESH_MS);
    return () => clearInterval(timer);
  }, [reload]);

  async function act(appt, status) {
    try {
      await api.setStatus(appt.id, status);
      toast(`Token #${appt.token_number} (${appt.patient.full_name}) ${ACTIONS[status].done}`);
      reload();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  const q = queue.data;
  return (
    <div className="queue">
      <LoadState loading={doctors.loading} error={doctors.error} onRetry={doctors.reload} />
      {doctors.data && (
        <div className="pills" role="tablist" aria-label="Doctor">
          {doctors.data.map((d) => (
            <button
              key={d.id}
              type="button"
              role="tab"
              aria-selected={d.id === doctorId}
              className={`pill${d.id === doctorId ? " pill-active" : ""}`}
              onClick={() => setDoctorId(d.id)}
            >
              {d.full_name}
              <small>{d.specialty}</small>
            </button>
          ))}
        </div>
      )}
      {doctors.data?.length === 0 && <p className="muted">No active doctors. Add one in the Doctors tab.</p>}

      {doctorId && <LoadState loading={queue.loading} error={queue.error} onRetry={reload} />}
      {q && (
        <div className="grid-2">
          <section className="card now-serving" aria-label="Now serving">
            <p className="eyebrow">
              Room {q.doctor.room} &middot; {q.date}
            </p>
            <h2>Now serving</h2>
            {q.now_serving ? (
              <>
                <div className="big-token">#{q.now_serving.token_number}</div>
                <p className="serving-name">{q.now_serving.patient.full_name}</p>
                <p className="muted">{q.now_serving.reason || "No reason given"}</p>
                <button type="button" className="btn btn-success" onClick={() => act(q.now_serving, "completed")}>
                  Complete visit
                </button>
              </>
            ) : (
              <p className="muted big-empty">Doctor is free</p>
            )}
            <div className="next-up">
              <span>Next up</span>
              <strong>{q.next_up ? `#${q.next_up.token_number} ${q.next_up.patient.full_name}` : "nobody waiting"}</strong>
            </div>
            <div className="waiting-count">
              <strong>{q.waiting_count}</strong> waiting
            </div>
          </section>

          <section className="card">
            <QueueList title="Waiting room" items={q.waiting} actions={["in_consultation", "no_show", "cancelled"]}
              onAct={act} empty="Nobody is waiting." />
            <QueueList title="Not arrived yet" items={q.not_arrived} actions={["checked_in", "no_show", "cancelled"]}
              onAct={act} empty="No more bookings today." />
            <QueueList title="Done today" items={q.done} actions={[]} onAct={act} empty="Nothing finished yet." />
          </section>
        </div>
      )}
    </div>
  );
}

function QueueList({ title, items, actions, onAct, empty }) {
  return (
    <div className="queue-list">
      <h3>
        {title} <span className="count">{items.length}</span>
      </h3>
      {items.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <ul>
          {items.map((a) => (
            <li key={a.id} className="queue-item">
              <span className="token">#{a.token_number}</span>
              <div className="queue-who">
                <strong>{a.patient.full_name}</strong>
                <span className="muted">
                  {formatSlot(a.slot_time)} {a.reason && <>&middot; {a.reason}</>}
                </span>
              </div>
              {actions.length === 0 ? (
                <StatusBadge status={a.status} />
              ) : (
                <div className="queue-actions">
                  {actions.map((s) => (
                    <button key={s} type="button" className={`btn btn-sm ${ACTIONS[s].style}`} onClick={() => onAct(a, s)}>
                      {ACTIONS[s].label}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
