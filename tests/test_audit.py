import json
import tempfile
import unittest
from pathlib import Path

from enterprise_agent_control_plane.audit import (
    AuditTrace,
    validate_trace,
    verify_event_chain,
)


def _valid_event(action: str, **details) -> dict:
    """Build a schema-valid event for each action, for targeted validator tests."""
    minimal = {
        "request.received": {"request": "r", "intent": "refund", "principal": "p"},
        "shortlist": {"capabilities": [], "reason": "why"},
        "flow.select": {"intent": "refund", "reason": "why"},
        "flow.execute": {"flow_id": "f", "steps": 1},
        "flow.step": {"step": "s", "capability": "c", "token_valid": True, "result_ref": None},
        "policy.decision": {
            "capability": "c", "principal": "p", "decision": "allow", "outcome": "allowed",
            "reason": "why", "token_valid": True, "policy_version": "af-x", "policy_thresholds": {},
        },
        "approval.request": {"capability": "c", "reason": "why"},
        "approval.resolved": {"capability": "c"},
        "output.frame": {"request": "r", "intent": "refund", "flow": "f", "status": "ok"},
    }[action]
    return {**minimal, **details}


class TestAuditModel(unittest.TestCase):
    # --- record / serialize / save round-trip (issue #9) ----------------------
    def test_record_and_as_dict(self):
        trace = AuditTrace("trace-1")
        trace.record("agent", "request.received", "ok", {"request": "r", "intent": "refund", "principal": "agent"})
        data = trace.as_dict()
        self.assertEqual(data["trace_id"], "trace-1")
        self.assertEqual(len(data["events"]), 1)
        event = data["events"][0]
        self.assertEqual(event["action"], "request.received")
        self.assertEqual(event["actor"], "agent")
        self.assertIn("hash", event)
        self.assertIn("prev_hash", event)

    def test_save_round_trip_uses_temp_path(self):
        trace = AuditTrace("trace-2")
        trace.record("agent", "shortlist", "ok", {"capabilities": ["a"], "reason": "why"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.json"
            trace.save(path)
            reloaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(reloaded, trace.as_dict())


class TestAuditSchema(unittest.TestCase):
    # --- schema validation (issue #112) ---------------------------------------
    def test_complete_trace_validates(self):
        trace = AuditTrace("ok")
        for action in ("request.received", "shortlist", "flow.select", "flow.execute",
                       "policy.decision", "output.frame"):
            trace.record("agent", action, "ok", _valid_event(action))
        result = trace.validate(require_complete=True)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.errors, [])

    def test_unknown_action_fails_validation(self):
        events = [{"action": "bogus.action", "details": {}, "ts": "t", "actor": "a", "outcome": "ok"}]
        result = validate_trace(events)
        self.assertFalse(result.ok)
        self.assertTrue(any("unknown action" in e for e in result.errors))

    def test_missing_required_field_fails_validation(self):
        # shortlist requires both 'capabilities' and 'reason'; drop 'reason'.
        events = [{"action": "shortlist", "details": {"capabilities": []},
                   "ts": "t", "actor": "a", "outcome": "ok"}]
        result = validate_trace(events)
        self.assertFalse(result.ok)
        self.assertTrue(any("reason" in e for e in result.errors))

    def test_incomplete_trace_fails_completeness(self):
        trace = AuditTrace("partial")
        trace.record("agent", "request.received", "ok", _valid_event("request.received"))
        result = trace.validate(require_complete=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("missing mandatory event" in e for e in result.errors))


class TestAuditHashChain(unittest.TestCase):
    # --- tamper-evident hash chain (issue #39) --------------------------------
    def _trace(self) -> AuditTrace:
        trace = AuditTrace("chain")
        trace.record("agent", "request.received", "ok", _valid_event("request.received"))
        trace.record("agent", "shortlist", "ok", _valid_event("shortlist"))
        trace.record("agent", "output.frame", "ok", _valid_event("output.frame"))
        return trace

    def test_unmodified_trace_verifies(self):
        self.assertTrue(self._trace().verify())

    def test_mutated_event_fails_verification(self):
        events = self._trace().as_dict()["events"]
        self.assertTrue(verify_event_chain(events))
        events[1]["details"]["reason"] = "tampered"
        self.assertFalse(verify_event_chain(events))

    def test_reordered_events_fail_verification(self):
        events = self._trace().as_dict()["events"]
        events[0], events[1] = events[1], events[0]
        self.assertFalse(verify_event_chain(events))


if __name__ == "__main__":
    unittest.main()
