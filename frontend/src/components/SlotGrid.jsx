import { formatSlot } from "../lib/format";

// The doctor's day as a grid of buttons: free slots are selectable,
// booked ones show their token, past ones are greyed out.
export default function SlotGrid({ slots, selected, onSelect }) {
  if (slots.length === 0) return <p className="muted">No slots on this day.</p>;
  return (
    <div className="slot-grid" role="listbox" aria-label="Available slots">
      {slots.map((slot) => {
        const free = slot.status === "free";
        const isSelected = selected === slot.time;
        return (
          <button
            key={slot.time}
            type="button"
            role="option"
            aria-selected={isSelected}
            className={`slot slot-${slot.status}${isSelected ? " slot-selected" : ""}`}
            disabled={!free}
            onClick={() => onSelect(slot.time)}
            title={slot.status === "booked" ? `Booked (token #${slot.token_number})` : slot.status}
          >
            <span>{formatSlot(slot.time)}</span>
            {slot.status === "booked" && <small>#{slot.token_number}</small>}
          </button>
        );
      })}
    </div>
  );
}
