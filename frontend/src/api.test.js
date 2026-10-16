import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorMessage } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("turns FastAPI error bodies into readable messages", () => {
    expect(errorMessage(409, { detail: "This slot is already booked" })).toBe("This slot is already booked");
    const validation = {
      detail: [{ loc: ["body", "phone"], msg: "Value error, phone must be a 10-digit Indian mobile number" }],
    };
    expect(errorMessage(422, validation)).toBe("phone: phone must be a 10-digit Indian mobile number");
    expect(errorMessage(500, null)).toBe("Request failed (500)");
  });

  it("calls relative /api URLs and throws ApiError on failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ detail: "This slot is already booked" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const call = api.book({ doctor_id: 1, patient_id: 2, appointment_date: "2030-01-15", slot_time: "10:00" });
    await expect(call).rejects.toBeInstanceOf(ApiError);
    await expect(call).rejects.toMatchObject({ status: 409, message: "This slot is already booked" });
    expect(fetchMock).toHaveBeenCalledWith("/api/appointments", expect.objectContaining({ method: "POST" }));
  });

  it("builds query strings and skips empty params", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve([]) });
    vi.stubGlobal("fetch", fetchMock);
    await api.patients("");
    await api.queue(3, "2030-01-15");
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(["/api/patients", "/api/queue?doctor_id=3&date=2030-01-15"]);
  });
});
