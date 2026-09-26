import pytest

from jarvis.brain import Brain, resolve_action
from jarvis.tools import ToolError
from tests.conftest import FakeClaude, response, text, tool_use


def test_plain_reply_and_request_shape(ctx):
    claude = FakeClaude(response(text("At your service.")))
    brain = Brain(ctx, client=claude)
    reply = brain.chat("Hello")
    assert reply.text == "At your service." and reply.actions == []
    req = claude.requests[0]
    assert req["model"] == "claude-opus-5"
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"] == {"effort": "medium"}
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    assert any(t.get("type") == "web_search_20260209" for t in req["tools"])
    assert "Tony" in req["system"]
    assert req["messages"][0]["content"][-1]["text"].endswith("] Hello")


def test_tool_loop_saves_and_uses_memory(ctx):
    claude = FakeClaude(
        response(tool_use("remember_fact", {"fact": "Tony's favourite colour is red"})),
        response(text("Noted.")),
    )
    brain = Brain(ctx, client=claude)
    assert brain.chat("My favourite colour is red").text == "Noted."
    tool_result = claude.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "Saved fact #1" in tool_result["content"]

    # A new conversation starts with the remembered facts.
    brain.reset()
    claude.responses.append(response(text("Red.")))
    brain.chat("What's my favourite colour?")
    first_turn = claude.requests[-1]["messages"][0]["content"]
    assert "favourite colour is red" in first_turn[0]["text"]


def test_history_persists_across_restarts(ctx):
    Brain(ctx, client=FakeClaude(response(text("Hi.")))).chat("Hello")
    brain = Brain(ctx, client=FakeClaude(response(text("Again."))))
    assert len(brain.messages) == 2
    brain.chat("Again")
    assert len(brain.messages) == 4


def test_tool_errors_are_reported_to_claude(ctx):
    claude = FakeClaude(response(tool_use("forget_fact", {"id": 42})), response(text("Nothing to forget.")))
    Brain(ctx, client=claude).chat("forget fact 42")
    result = claude.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "No fact #42" in result["content"]


def test_sensitive_action_is_queued_then_approved(phone_ctx, twilio):
    ctx = phone_ctx
    ctx.db.execute("INSERT INTO contacts (name, phone, created_at) VALUES ('Pepper', '+15559998888', 'x')")
    claude = FakeClaude(
        response(tool_use("call_contact", {"who": "Pepper", "message": "Tony is running late"})),
        response(text("I'll call Pepper once you approve.")),
    )
    reply = Brain(ctx, client=claude).chat("Call Pepper and say I'm late")
    assert len(reply.actions) == 1 and "Pepper" in reply.actions[0]["summary"]
    assert twilio.calls_made == []  # nothing happens without approval

    _, result = resolve_action(ctx, reply.actions[0]["id"], approve=True)
    assert "Calling Pepper" in result and twilio.calls_made[0]["to"] == "+15559998888"
    with pytest.raises(ToolError, match="already"):
        resolve_action(ctx, reply.actions[0]["id"], approve=True)


def test_cli_approver_can_decline(phone_ctx, twilio):
    claude = FakeClaude(
        response(tool_use("text_contact", {"who": "+15559998888", "message": "hi"})),
        response(text("Understood, I won't.")),
    )
    Brain(phone_ctx, client=claude, approver=lambda *a: False).chat("text them")
    assert twilio.texts_sent == []
    assert "declined" in claude.requests[1]["messages"][-1]["content"][0]["content"]


def test_refusal_and_errors_roll_back_history(ctx):
    brain = Brain(ctx, client=FakeClaude(response(text(""), stop_reason="refusal")))
    assert "can't help" in brain.chat("something bad").text
    assert brain.messages == []

    class Boom(FakeClaude):
        def _create(self, **params):
            raise RuntimeError("network down")

    brain = Brain(ctx, client=Boom())
    with pytest.raises(RuntimeError):
        brain.chat("hello")
    assert brain.messages == []


def test_pause_turn_resumes(ctx):
    claude = FakeClaude(response(text("Searching…"), stop_reason="pause_turn"), response(text("Found it.")))
    assert Brain(ctx, client=claude).chat("search").text == "Found it."
    assert len(claude.requests) == 2
