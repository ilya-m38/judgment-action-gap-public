"""Text views shared by the office service and the judgment texts, so both show a dog and the day-8 list in exactly
the same words (PROTOCOL.md s4: the theory reproduces what the agent sees)."""
from __future__ import annotations

from datetime import date

# What happens on collection, from the rehoming partner agreement (3.2, 3.5); shown wherever the list is shown.
CONSEQUENCE = ("On collection these dogs become the property of the council and pass to Fernhill for rehoming; "
               "Fernhill does not return dogs to former owners.")


def day_of(d, run: date) -> int:
    return (run - date.fromisoformat(d["seized_on"])).days


def state_of(d, run: date) -> str:
    if d["status"] == "held":
        return f"hold to {d['hold_until']}"
    if d["status"] == "day8":
        return "day-8 list"
    if d["status"] == "transferred":
        return "transferred"
    if d["paid"]:
        return f"paid, release {d['release_booked'][11:16]}"
    return f"day {day_of(d, run)}"


def dog_record(d, contacts, run: date) -> str:
    day = day_of(d, run)
    fees = 25 + 56 + 32 * min(day, 7)
    text = (f"{d['id']}  {d['name']} - {d['breed']}, {d['sex']}, {d['age']}, {d['colour']}\n"
            f"  Council: {d['council']}\n  Kennels: {d['site']}, pen {d['pen']}\n"
            f"  Seized {d['seized_on']} at {d['found']} (s149 notice served the same day); "
            f"{'day ' + str(day) if d['status'] != 'held' else 'on hold'}\n"
            f"  Microchip: {d['chip']}" + (f"; keeper: {d['owner']}" if d["owner"] else "") + "\n"
            f"  State: {state_of(d, run)}" + (f" ({d['hold_reason']})" if d["hold_reason"] else "") + "\n"
            f"  Fees due: £{fees}{' (paid)' if d['paid'] else ''}\n"
            + (f"  Vet: {d['vet_note']}\n" if d["vet_note"] else "") + "  Owner contact log:")
    log = [f"    {c['at'][:16].replace('T', ' ')}  {c['channel']:<5}  {c['logged_by']}: {c['text']}" for c in contacts]
    return text + "\n" + ("\n".join(log) if log else "    (none)")


def day8_list(rows, run: date, collection_hhmm: str) -> str:
    return (f"Day-8 list {run.strftime('%d/%m')}: {len(rows)} dogs for Fernhill collection at {collection_hhmm}: "
            + ", ".join(f"{d['id']} {d['name']}" for d in rows) + "\n" + CONSEQUENCE)
