from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from .config import load_flow_definitions
from .errors import ErrorCode, StepStatus, error, is_error
from .registry import bind_step_args, validate_step_input


@dataclass(frozen=True)
class FlowStep:
    name: str
    capability: str


@dataclass(frozen=True)
class FlowDefinition:
    flow_id: str
    steps: list[FlowStep]
    # The write/destructive capabilities this flow performs, each of which must pass its own
    # policy decision before it can take effect (issue #66). The governed path derives the
    # set of actions to gate from this declaration rather than a per-intent hardcode, so a
    # flow that touches two writes gates both -- no write can run ungated.
    gated_capabilities: tuple[str, ...] = ()


def _build_flow_registry() -> dict[str, FlowDefinition]:
    """Build the flow registry from ``flows/*.flow.yaml`` -- the single source of truth (#3).

    The YAML files drive the registry directly; there is no hardcoded Python mirror to drift
    from them. ``tests/test_yaml_parity.py`` (issue #148) guards that every step/gated
    capability names a real registry capability.
    """
    registry: dict[str, FlowDefinition] = {}
    for flow_id, spec in load_flow_definitions().items():
        registry[flow_id] = FlowDefinition(
            flow_id=flow_id,
            steps=[FlowStep(name, capability) for name, capability in spec["steps"]],
            gated_capabilities=spec["gated_capabilities"],
        )
    return registry


FLOW_REGISTRY: dict[str, FlowDefinition] = _build_flow_registry()


# Intent -> governed flow (issue #25). The governed path makes a single deterministic
# routing decision (which known workflow to run); the inner steps then execute with no
# further per-step model routing.
INTENT_FLOWS: dict[str, str] = {
    "refund": "refund_review",
    "refund_notify": "refund_and_notify",
    "reply": "customer_reply",
    "escalation": "escalation",
}


def classify_intent(request: str) -> "str | None":
    """Map a free-text request to a known intent, or ``None`` if unsupported."""
    text = request.lower()
    if "refund" in text:
        # A refund that also asks to notify/confirm the customer routes to the two-write
        # flow so both the refund and the confirmation send are gated (issue #66).
        if "notify" in text or "confirm" in text:
            return "refund_notify"
        return "refund"
    if "escalat" in text or "ticket" in text:
        return "escalation"
    if "reply" in text or "email" in text or "send" in text:
        return "reply"
    return None


def select_flow(request: str) -> "tuple[str | None, str | None]":
    """Select one registered flow for a request via a single deterministic decision.

    Returns ``(intent, flow_id)``. An unsupported request yields ``(None, None)`` so
    the caller can surface an explicit "no matching governed flow" outcome rather than
    defaulting silently (issue #25).
    """
    intent = classify_intent(request)
    if intent is None:
        return None, None
    return intent, INTENT_FLOWS.get(intent)


class ChainWeaverExecutor:
    """ChainWeaver-style deterministic runner with no LLM between steps."""

    def __init__(self, tools: dict[str, Callable[..., Any]]):
        self.tools = tools

    def run(
        self,
        flow_id: str,
        payload: dict[str, Any],
        token_check: Callable[[str], bool] | None = None,
        on_step: Callable[[dict[str, Any]], None] | None = None,
        budget: Optional["set[str] | frozenset[str]"] = None,
    ) -> list[dict[str, Any]]:
        """Run a flow deterministically, optionally gating each step on a capability token.

        ``token_check`` (issue #111) is consulted before a step runs: a step whose
        capability the principal does not hold a token for *fails closed* -- the tool is not
        invoked, and the step record is marked ``token_valid=False`` with a blocked status.
        ``on_step`` is called once per step (executed or blocked) so the caller can record a
        per-step audit event. With neither argument the runner behaves as a plain executor.

        ``budget`` (issue #110) is the case's authoritative capability budget — the bounded
        shortlist made enforceable. When supplied, the executor may only invoke capabilities
        in the budget; a step that needs a capability the shortlist did not surface *fails
        closed* (status ``failed`` with an ``out_of_budget`` error) and halts the flow, rather
        than silently widening exposure to the full tool map. ``budget=None`` disables the
        check (a plain executor).

        Each step's inputs are validated against the capability's declared schema *before* the
        tool runs (issues #4/#162): a missing or wrong-typed field fails the step closed with an
        ``invalid_input`` error instead of the unhandled ``KeyError`` the old dispatcher raised.

        A step that fails -- validation fails, the tool returns an ``{"error": ...}`` payload,
        or it raises -- halts the flow closed (issue #41): the failing step is recorded with
        status ``failed`` and no later step runs, so a bad dependency can never reach a
        downstream write.

        Note the two fail-closed mechanisms are deliberately distinct: a token-blocked step
        (``token_valid=False``) is per-step least privilege (#111) -- it is skipped and the
        flow *continues*, since one un-held read need not abort the run -- whereas a *failed*
        step (#41/#110) halts the whole flow. Either way the tool's side effect never fires.
        """
        flow = FLOW_REGISTRY[flow_id]
        results: list[dict[str, Any]] = []
        for step in flow.steps:
            if budget is not None and step.capability not in budget:
                # Out of budget: the shortlist never surfaced this capability, so the flow
                # fails closed here rather than reaching beyond the bounded budget (issue #110).
                record = self._record(
                    step,
                    output=error(
                        ErrorCode.OUT_OF_BUDGET,
                        detail=f"{step.capability} is outside the case capability budget",
                    ),
                    token_valid=True,
                    status=StepStatus.FAILED,
                )
                results.append(record)
                if on_step is not None:
                    on_step(record)
                break
            token_valid = True if token_check is None else token_check(step.capability)
            if not token_valid:
                # Fail closed: no token, so the tool never runs (issue #111).
                record = self._record(
                    step, output=None, token_valid=False, status=StepStatus.BLOCKED_NO_TOKEN
                )
                results.append(record)
                if on_step is not None:
                    on_step(record)
                continue
            out = self._invoke_step(step.capability, payload)
            failed = is_error(out)
            record = self._record(
                step,
                output=out,
                token_valid=True,
                status=StepStatus.FAILED if failed else StepStatus.OK,
            )
            results.append(record)
            if on_step is not None:
                on_step(record)
            if failed:
                # Fail closed on the first failed step: no later (possibly write) step runs.
                break
        return results

    @staticmethod
    def _record(
        step: FlowStep, output: Any, token_valid: bool, status: StepStatus
    ) -> dict[str, Any]:
        return {
            "step": step.name,
            "capability": step.capability,
            "output": output,
            "token_valid": token_valid,
            "status": status.value,
        }

    def _invoke_step(self, capability: str, payload: dict[str, Any]) -> Any:
        """Invoke one flow step, validating and binding its args from the registry (#149).

        The per-capability ``if/elif`` this method used to be -- including the unreachable
        ``support.create_task`` branch (issue #165) -- is gone: the call is derived from the
        capability's ``args_schema`` / ``step_defaults`` via :func:`registry.bind_step_args`,
        so a new flow step needs no code change here. Inputs are schema-validated first
        (issues #4/#162), and any tool exception is converted to a structured failure (#41).
        """
        tool = self.tools.get(capability)
        if tool is None:
            return error(ErrorCode.UNKNOWN_STEP, capability=capability)
        invalid = validate_step_input(capability, payload)
        if invalid is not None:
            return invalid
        try:
            return tool(*bind_step_args(capability, payload))
        except Exception as exc:  # noqa: BLE001 - convert any tool error into a structured failure
            return error(ErrorCode.EXCEPTION, capability=capability, detail=str(exc))
