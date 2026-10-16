import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import StatsBar from "./components/StatsBar";
import { ToastProvider } from "./lib/toast";
import BookView from "./views/BookView";
import DoctorsView from "./views/DoctorsView";
import PatientsView from "./views/PatientsView";
import QueueView from "./views/QueueView";

const TABS = [
  { id: "book", label: "Book appointment", View: BookView },
  { id: "queue", label: "Live queue", View: QueueView },
  { id: "patients", label: "Patients", View: PatientsView },
  { id: "doctors", label: "Doctors", View: DoctorsView },
];

// The tab lives in the URL hash (#queue) so a reception screen can bookmark it.
function tabFromHash() {
  const id = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === id) ? id : "book";
}

export default function App() {
  const [tab, setTab] = useState(tabFromHash);
  const [stats, setStats] = useState(null);

  const refreshStats = useCallback(() => {
    api.stats().then(setStats, () => setStats(null));
  }, []);

  useEffect(() => {
    refreshStats();
    const timer = setInterval(refreshStats, 15000);
    return () => clearInterval(timer);
  }, [refreshStats]);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const { View } = TABS.find((t) => t.id === tab);

  return (
    <ToastProvider>
      <header className="header">
        <div className="brand">
          <div className="logo" aria-hidden="true">+</div>
          <div>
            <h1>CareQueue</h1>
            <p>Clinic Appointments &amp; Patient Queue{stats ? ` · ${stats.date}` : ""}</p>
          </div>
        </div>
        <StatsBar stats={stats} />
      </header>
      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <a key={t.id} href={`#${t.id}`} className={`tab${t.id === tab ? " tab-active" : ""}`}
            aria-current={t.id === tab ? "page" : undefined}>
            {t.label}
          </a>
        ))}
      </nav>
      <main className="main">
        <View onChange={refreshStats} />
      </main>
    </ToastProvider>
  );
}
