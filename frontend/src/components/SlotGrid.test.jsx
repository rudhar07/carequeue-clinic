import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import SlotGrid from "./SlotGrid";

const slots = [
  { time: "09:00:00", status: "past", token_number: null },
  { time: "09:15:00", status: "booked", token_number: 4 },
  { time: "09:30:00", status: "free", token_number: null },
];

describe("SlotGrid", () => {
  it("only lets free slots be picked", async () => {
    const onSelect = vi.fn();
    render(<SlotGrid slots={slots} selected={null} onSelect={onSelect} />);

    expect(screen.getByRole("option", { name: /9:00 AM/ })).toBeDisabled();
    expect(screen.getByRole("option", { name: /9:15 AM/ })).toBeDisabled();
    expect(screen.getByText("#4")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("option", { name: /9:30 AM/ }));
    expect(onSelect).toHaveBeenCalledWith("09:30:00");
  });

  it("marks the selected slot", () => {
    render(<SlotGrid slots={slots} selected="09:30:00" onSelect={() => {}} />);
    expect(screen.getByRole("option", { name: /9:30 AM/ })).toHaveAttribute("aria-selected", "true");
  });
});
