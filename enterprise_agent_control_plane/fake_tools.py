from typing import Any


# NOTE: every value below is obviously synthetic ("[FAKE]" / example.com). The extra
# internal-style fields (notes, risk flags, payment fragments, history) exist so the
# unsafe baseline has something realistic to over-expose: it forwards these complete
# records into model context verbatim, with no field projection (issue #16). The
# governed path's bounded Frame would project only task-relevant fields instead.
CUSTOMERS = {
    "C-100": {
        "customer_id": "C-100",
        "name": "Ari Carter",
        "tier": "gold",
        "email": "ari@example.com",
        "phone": "[FAKE] +1-555-0100",
        "internal_notes": "[FAKE] flagged as repeat refund requester; watch for abuse",
        "risk_flags": ["[FAKE] chargeback_history", "[FAKE] manual_review"],
        "payment_method": "[FAKE] card ****-****-****-4242",
        "account_history": ["[FAKE] 2023-01 opened account", "[FAKE] 2024-06 refunded $50"],
    },
}

INVOICES = {
    "INV-9": {
        "invoice_id": "INV-9",
        "customer_id": "C-100",
        "amount": 149.0,
        "status": "paid",
        "payment_method": "[FAKE] card ****-****-****-4242",
        "billing_address": "[FAKE] 1 Example Way, Springfield",
        "internal_margin": "[FAKE] 0.62",
        "fraud_score": "[FAKE] 0.08",
    },
}

TICKETS = {
    "C-100": [
        {
            "ticket_id": "T-7",
            "subject": "Late shipment",
            "status": "closed",
            "agent_comments": "[FAKE] customer was rude; consider goodwill credit",
            "internal_priority": "[FAKE] P3",
        }
    ],
}

SENT_EMAILS: list[dict[str, Any]] = []
TASKS: list[dict[str, Any]] = []
REFUNDS: list[dict[str, Any]] = []


def reset_state() -> None:
    """Clear module-level mutable state for test isolation."""
    SENT_EMAILS.clear()
    TASKS.clear()
    REFUNDS.clear()


def crm_search_customer(customer_id: str) -> dict[str, Any]:
    return CUSTOMERS.get(customer_id, {"error": "not_found", "customer_id": customer_id})


def billing_get_invoice(invoice_id: str) -> dict[str, Any]:
    return INVOICES.get(invoice_id, {"error": "not_found", "invoice_id": invoice_id})


def billing_issue_refund(invoice_id: str, amount: float, reason: str) -> dict[str, Any]:
    refund = {"invoice_id": invoice_id, "amount": amount, "reason": reason, "status": "issued"}
    REFUNDS.append(refund)
    return refund


def support_search_tickets(customer_id: str) -> list[dict[str, Any]]:
    return TICKETS.get(customer_id, [])


def support_create_task(customer_id: str, note: str) -> dict[str, Any]:
    task = {"task_id": f"TASK-{len(TASKS) + 1}", "customer_id": customer_id, "note": note}
    TASKS.append(task)
    return task


def email_draft_reply(customer_name: str, topic: str) -> dict[str, Any]:
    return {"subject": f"Update on your request: {topic}", "body": f"Hi {customer_name},\\nWe reviewed your request."}


def email_send_reply(to: str, subject: str, body: str) -> dict[str, Any]:
    email = {"to": to, "subject": subject, "body": body, "status": "sent"}
    SENT_EMAILS.append(email)
    return email


def docs_search_policy(query: str) -> list[dict[str, Any]]:
    return [{"policy_id": "P-REFUND-001", "title": "Refund approvals", "snippet": f"Match for: {query}"}]


def audit_export_case(case_id: str) -> dict[str, Any]:
    return {"case_id": case_id, "export_status": "ready"}
