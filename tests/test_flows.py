import unittest

from enterprise_agent_control_plane import fake_tools
from enterprise_agent_control_plane.flows import ChainWeaverExecutor


class TestFlows(unittest.TestCase):
    def test_refund_review_flow_is_deterministic(self):
        tools = {
            "crm.search_customer": fake_tools.crm_search_customer,
            "billing.get_invoice": fake_tools.billing_get_invoice,
            "docs.search_policy": fake_tools.docs_search_policy,
            "email.draft_reply": fake_tools.email_draft_reply,
            "support.search_tickets": fake_tools.support_search_tickets,
            "support.create_task": fake_tools.support_create_task,
        }
        runner = ChainWeaverExecutor(tools)
        result = runner.run("refund_review", {"customer_id": "C-100", "invoice_id": "INV-9", "customer_name": "Ari Carter"})
        self.assertEqual([s["step"] for s in result], ["lookup_customer", "lookup_invoice", "check_policy", "draft_reply"])


if __name__ == "__main__":
    unittest.main()
