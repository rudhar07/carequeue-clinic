// Thin wrapper around fetch. Every call is relative (/api/...): nginx (Docker,
// Kubernetes) or the Vite dev server forwards it to the FastAPI backend.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// FastAPI returns {"detail": "text"} for our own errors and
// {"detail": [{loc, msg}, ...]} for validation errors.
export function errorMessage(status, body) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "";
        const msg = String(d.msg || "invalid").replace(/^Value error, /, "");
        return field && field !== "body" ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new ApiError(0, "Cannot reach the CareQueue server");
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, data));
  return data;
}

function query(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries)}` : "";
}

export const api = {
  stats: () => request("GET", "/stats/today"),

  doctors: (params = {}) => request("GET", `/doctors${query(params)}`),
  createDoctor: (body) => request("POST", "/doctors", body),
  updateDoctor: (id, body) => request("PUT", `/doctors/${id}`, body),
  deleteDoctor: (id) => request("DELETE", `/doctors/${id}`),
  slots: (doctorId, date) => request("GET", `/doctors/${doctorId}/slots${query({ date })}`),

  patients: (q) => request("GET", `/patients${query({ q })}`),
  createPatient: (body) => request("POST", "/patients", body),
  updatePatient: (id, body) => request("PUT", `/patients/${id}`, body),
  deletePatient: (id) => request("DELETE", `/patients/${id}`),

  book: (body) => request("POST", "/appointments", body),
  setStatus: (id, status) => request("PATCH", `/appointments/${id}/status`, { status }),
  queue: (doctorId, date) => request("GET", `/queue${query({ doctor_id: doctorId, date })}`),
};
