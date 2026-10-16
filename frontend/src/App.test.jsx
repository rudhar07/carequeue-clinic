import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const DOCTOR = {
  id: 1, full_name: "Dr. Ananya Iyer", specialty: "General Medicine", room: "101",
  slot_minutes: 15, start_time: "09:00:00", end_time: "17:00:00", is_active: true,
};
const PATIENT = { id: 7, full_name: "Priya Sharma", phone: "9876500001", date_of_birth: "1991-04-12", gender: "female" };
const STATS = {
  date: "2030-01-15", total: 9, active_doctors: 4, patients: 12,
  by_status: { booked: 2, checked_in: 3, in_consultation: 1, completed: 2, cancelled: 0, no_show: 1 },
};
const appt = (token, status) => ({
  id: token, token_number: token, status, slot_time: "10:00:00", reason: "Fever",
  appointment_date: "2030-01-15", patient: PATIENT, doctor: DOCTOR,
});

// A tiny fake backend keyed by URL path.
function fakeFetch(url) {
  const path = url.split("?")[0];
  const routes = {
    "/api/stats/today": STATS,
    "/api/doctors": [DOCTOR],
    "/api/doctors/1/slots": { doctor_id: 1, date: "2030-01-15", slot_minutes: 15, free_count: 1,
      slots: [{ time: "10:00:00", status: "free", token_number: null }] },
    "/api/patients": [PATIENT],
    "/api/queue": { doctor: DOCTOR, date: "2030-01-15", now_serving: appt(4, "in_consultation"),
      next_up: appt(5, "checked_in"), waiting_count: 1, waiting: [appt(5, "checked_in")], not_arrived: [], done: [] },
  };
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(routes[path]) });
}

beforeEach(() => {
  window.location.hash = "";
  vi.stubGlobal("fetch", vi.fn(fakeFetch));
});
afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("shows the clinic header with today's stats and the booking slot grid", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "CareQueue" })).toBeInTheDocument();
    const stats = await screen.findByLabelText("Today's statistics");
    expect(stats).toHaveTextContent("Appointments9");
    expect(await screen.findByRole("option", { name: /10:00 AM/ })).toBeEnabled();
  });

  it("switches to the live queue and shows who is being served", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("link", { name: "Live queue" }));
    expect(await screen.findByText("#4")).toBeInTheDocument();
    expect(screen.getByText("Now serving")).toBeInTheDocument();
    expect(screen.getByText("#5 Priya Sharma")).toBeInTheDocument();
  });

  it("lists patients with formatted phone numbers", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("link", { name: "Patients" }));
    await waitFor(() => expect(screen.getByText(/98765 00001/)).toBeInTheDocument());
  });
});
