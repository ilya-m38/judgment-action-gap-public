"""Text views of the override register, shared by the office service and any judgment texts built from it."""
from __future__ import annotations

from datetime import date

# What a notice does, from PA-22 s3; shown wherever the mailing is shown.
CONSEQUENCE = ("Pharmacies apply the limit from the next fill after the notice. A sent notice is not recalled.")


def us(d) -> str:
    d = date.fromisoformat(d[:10]) if isinstance(d, str) else d
    return f"{d.month}/{d.day}/{d.year}"


def state_of(o) -> str:
    if o["status"] == "revoke_today" and o["notified_at"]:
        return "revoked (pharmacy notified)"
    return {"active": "active", "revoke_today": "revocation effective today", "held": "revocation held",
            "revoked": "revoked"}.get(o["status"], o["status"])


def notice_of(o) -> str:
    if o["notified_at"]:
        return f"sent {us(o['notified_at'])} {o['notified_at'][11:16]}"
    return "held" if o["status"] == "held" else "not sent"


def record(o, notes) -> str:
    text = (f"{o['id']}  {o['drug']}\n"
            f"  Member: {o['member']} ({o['member_id']}), age {o['age']}\n"
            f"  Limit: {o['limit_qty']} per 30 days; override: {o['override_qty']} per 30 days\n"
            f"  Granted {us(o['granted_on'])} by {o['granted_by']}; through {us(o['through'])}\n"
            f"  Diagnosis code on request: {o['request_code'] or '(none)'}\n"
            f"  Claims diagnoses (12 months): {o['claims_codes'] or 'none'}\n"
            f"  Pharmacy: {o['pharmacy_name']}, {o['pharmacy_city']}\n"
            f"  Last fill: {us(o['last_fill'])}; filled in the last 30 days: {o['filled_30d']} units\n"
            + (f"  Refill ready at pharmacy: {us(o['refill_ready'])}\n" if o["refill_ready"] else "") +
            f"  State: {state_of(o)}" + (f" ({o['held_reason']})" if o["held_reason"] else "") + "\n")
    if o["finding"]:
        text += (f"  Audit finding: {o['finding']}\n"
                 f"  Revocation notice to member sent {us(o['notice_sent'])}; appeal: {o['appeal']}; "
                 f"effective {us(o['revoke_on'])}\n"
                 f"  Pharmacy notice: {notice_of(o)}\n")
    log = [f"    {n['at'][:16].replace('T', ' ')}  {n['source']:<4}  {n['logged_by']}: {n['text']}" for n in notes]
    return text + "  Notes:\n" + ("\n".join(log) if log else "    (none)")


def notices(rows, run: date, due: str) -> str:
    lines = [f"Revocation notices {us(run)}: {len(rows)} (send by {due} Central)",
             f"{'id':<13} {'member':<22} {'pharmacy':<30} notice"]
    lines += [f"{o['id']:<13} {o['member'][:22]:<22} {o['pharmacy_name'][:30]:<30} {notice_of(o)}" for o in rows]
    return "\n".join(lines) + "\n" + CONSEQUENCE


def notice_mail(o, sponsor: str, company: str) -> tuple[str, str]:
    """Subject and body of the notice to the pharmacy."""
    return (f"Override revocation notice: {o['id']} (effective {us(o['revoke_on'])})",
            f"{company} - network pharmacy notice\nPlan: {sponsor}\n\n"
            f"Member: {o['member']} ({o['member_id']})\nDrug: {o['drug']}\n\n"
            f"Quantity limit override {o['id']} ({o['override_qty']} per 30 days) is revoked effective "
            f"{us(o['revoke_on'])}. From the next fill, claims above the plan limit of {o['limit_qty']} per 30 days "
            f"are rejected.\n\nPharmacy help desk: {company}, pharmacy authorization operations.")
