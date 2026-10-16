import { describe, expect, it } from "vitest";
import { ageFrom, formatPhone, formatSlot, isoDate } from "./format";

describe("format helpers", () => {
  it("formats slot times as 12-hour clock", () => {
    expect(formatSlot("09:00:00")).toBe("9:00 AM");
    expect(formatSlot("12:15:00")).toBe("12:15 PM");
    expect(formatSlot("16:45")).toBe("4:45 PM");
    expect(formatSlot("00:30:00")).toBe("12:30 AM");
  });

  it("computes age in whole years around the birthday", () => {
    expect(ageFrom("1991-04-12", new Date(2026, 3, 11))).toBe(34);
    expect(ageFrom("1991-04-12", new Date(2026, 3, 12))).toBe(35);
  });

  it("formats phones and local dates", () => {
    expect(formatPhone("9876543210")).toBe("98765 43210");
    expect(isoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});
