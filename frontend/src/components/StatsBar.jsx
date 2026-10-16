// Today's numbers shown in the header (refreshed by App).
export default function StatsBar({ stats }) {
  if (!stats) return <div className="stats stats-empty">Loading today's numbers...</div>;
  const s = stats.by_status;
  const items = [
    ["Appointments", stats.total],
    ["Waiting", s.checked_in],
    ["With doctor", s.in_consultation],
    ["Completed", s.completed],
    ["No-show", s.no_show],
  ];
  return (
    <dl className="stats" aria-label="Today's statistics">
      {items.map(([label, value]) => (
        <div className="stat" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
