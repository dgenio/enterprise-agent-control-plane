from typing import Any

from .catalog import build_catalog
from . import fake_tools


class BaselineAgent:
    """Unsafe baseline: broad tools, raw outputs, no policy/audit/deterministic flow."""

    def __init__(self):
        self.catalog = build_catalog()
        self.tools = {
            "crm.search_customer": fake_tools.crm_search_customer,
            "billing.get_invoice": fake_tools.billing_get_invoice,
            "billing.issue_refund": fake_tools.billing_issue_refund,
            "support.search_tickets": fake_tools.support_search_tickets,
            "support.create_task": fake_tools.support_create_task,
            "email.draft_reply": fake_tools.email_draft_reply,
            "email.send_reply": fake_tools.email_send_reply,
            "docs.search_policy": fake_tools.docs_search_policy,
            "audit.export_case": fake_tools.audit_export_case,
        }

    def run_case(self, customer_id: str, invoice_id: str) -> dict[str, Any]:
        customer = self.tools["crm.search_customer"](customer_id)
        invoice = self.tools["billing.get_invoice"](invoice_id)
        refund_attempt = self.tools["billing.issue_refund"](invoice_id, 149.0, "customer requested")
        return {
            "mode": "unsafe",
            "visible_tools": [c.capability for c in self.catalog],
            "raw_outputs": {"customer": customer, "invoice": invoice, "refund_attempt": refund_attempt},
        }
