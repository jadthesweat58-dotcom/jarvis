from types import SimpleNamespace

import pytest
from google.genai import types

from jarvis.brain import create_brain, resolve_action
from jarvis.config import DEFAULT_MODELS, Settings
from jarvis.gemini_brain import GeminiBrain


def reply(*parts, finish="STOP"):
    return types.GenerateContentResponse.model_validate(
        {"candidates": [{"content": {"role": "model", "parts": list(parts)}, "finish_reason": finish}]}
    )


def call(name, args, id="call_1", signature="c2lnbmF0dXJl"):
    return {"function_call": {"id": id, "name": name, "args": args}, "thought_signature": signature}


class FakeGemini:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, *, model, contents, config):
        self.requests.append({"model": model, "config": config,
                              "contents": [c.model_dump(mode="json", exclude_none=True) if hasattr(c, "model_dump") else c
                                           for c in (contents if isinstance(contents, list) else [contents])]})
        return self.responses.pop(0)


@pytest.fixture
def gctx(ctx):
    ctx.settings.provider = "gemini"
    ctx.settings.model = "gemini-3.8-flash"
    ctx.settings.gemini_api_key = "test"
    return ctx


def test_create_brain_picks_provider(gctx, ctx):
    assert isinstance(create_brain(gctx), GeminiBrain)
    assert Settings(provider="claude", model="").model == DEFAULT_MODELS["claude"]
    assert Settings(provider="gemini", model="").model == "gemini-3.8-flash"
    with pytest.raises(ValueError):
        Settings(provider="grok")


def test_tool_loop_keeps_thought_signatures(gctx):
    gemini = FakeGemini(
        reply(call("remember_fact", {"fact": "Favourite colour is blue"})),
        reply({"text": "Noted, Tony."}),
    )
    brain = GeminiBrain(gctx, client=gemini)
    assert brain.chat("My favourite colour is blue").text == "Noted, Tony."

    first = gemini.requests[0]
    assert first["model"] == "gemini-3.8-flash"
    assert first["config"].thinking_config.thinking_level == types.ThinkingLevel.MEDIUM
    assert first["config"].automatic_function_calling.disable is True
    names = {d.name for d in first["config"].tools[0].function_declarations}
    assert {"remember_fact", "set_reminder", "web_search"} <= names
    assert "Tony" in first["config"].system_instruction

    second = gemini.requests[1]["contents"]
    assert second[1]["parts"][0]["thought_signature"] == "c2lnbmF0dXJl"  # sent back unchanged
    response = second[2]["parts"][0]["function_response"]
    assert response["id"] == "call_1" and response["name"] == "remember_fact"
    assert "Saved fact #1" in response["response"]["result"]
    assert gctx.db.one("SELECT fact FROM facts")["fact"] == "Favourite colour is blue"


def test_history_survives_restart_and_facts_start_new_conversations(gctx):
    GeminiBrain(gctx, client=FakeGemini(reply({"text": "Hello."}))).chat("hi")
    gemini = FakeGemini(reply({"text": "Again."}))
    brain = GeminiBrain(gctx, client=gemini)
    brain.chat("again")
    assert [m["role"] for m in gemini.requests[0]["contents"]] == ["user", "model", "user"]

    gctx.db.execute("INSERT INTO facts (fact, category, created_at) VALUES ('Lives in Dubai', 'personal', 'x')")
    brain.reset()
    gemini.responses.append(reply({"text": "Dubai."}))
    brain.chat("where do I live?")
    assert "Lives in Dubai" in gemini.requests[-1]["contents"][0]["parts"][0]["text"]


def test_tool_errors_and_thoughts(gctx):
    gemini = FakeGemini(
        reply(call("forget_fact", {"id": 42})),
        reply({"text": "(thinking)", "thought": True}, {"text": "Nothing to forget."}),
    )
    assert GeminiBrain(gctx, client=gemini).chat("forget 42").text == "Nothing to forget."
    response = gemini.requests[1]["contents"][-1]["parts"][0]["function_response"]["response"]
    assert "No fact #42" in response["error"]


def test_blocked_reply_rolls_back(gctx):
    blocked = types.GenerateContentResponse.model_validate({"candidates": [{"finish_reason": "SAFETY"}]})
    brain = GeminiBrain(gctx, client=FakeGemini(blocked))
    assert "can't help" in brain.chat("something bad").text
    assert brain.messages == []


def test_approval_flow(gctx, twilio):
    s = gctx.settings
    s.twilio_account_sid, s.twilio_auth_token, s.twilio_phone_number = "AC1", "secret", "+15550000000"
    gctx.db.execute("INSERT INTO contacts (name, phone, created_at) VALUES ('Mom', '+971501234567', 'x')")
    gemini = FakeGemini(reply(call("call_contact", {"who": "Mom", "message": "Running late"})),
                        reply({"text": "I'll call once you approve."}))
    out = GeminiBrain(gctx, client=gemini).chat("call mom")
    assert len(out.actions) == 1 and "+971501234567" in out.actions[0]["summary"]
    assert twilio.calls_made == []
    resolve_action(gctx, out.actions[0]["id"], approve=True)
    assert twilio.calls_made[0]["to"] == "+971501234567"


def test_web_search_uses_google_search_grounding(gctx):
    grounded = types.GenerateContentResponse.model_validate({"candidates": [{
        "content": {"role": "model", "parts": [{"text": "It's 34°C and sunny in Dubai."}]},
        "grounding_metadata": {"grounding_chunks": [{"web": {"uri": "https://x", "title": "weather.com"}}]},
    }]})
    gemini = FakeGemini(reply(call("web_search", {"query": "Dubai weather"})), grounded, reply({"text": "34 and sunny."}))
    assert GeminiBrain(gctx, client=gemini).chat("weather?").text == "34 and sunny."
    search_request = gemini.requests[1]
    assert search_request["config"].tools[0].google_search is not None
    result = gemini.requests[2]["contents"][-1]["parts"][0]["function_response"]["response"]["result"]
    assert "34°C" in result and "weather.com" in result


def test_gemini_looks_at_the_screen(gctx):
    gemini = FakeGemini(reply({"text": "A spreadsheet with Q3 sales of 1.2M."}), reply({"text": "Q3 sales were 1.2 million."}))
    out = GeminiBrain(gctx, client=gemini).chat("what were Q3 sales?", image=(b"\x89PNGfake", "image/png"))
    assert out.text == "Q3 sales were 1.2 million."
    look = gemini.requests[0]["contents"]
    assert look[0]["inline_data"]["mime_type"] == "image/png"
    assert gemini.requests[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert "1.2M" in gemini.requests[1]["contents"][-1]["parts"][-1]["text"]


def test_gemini_usage_is_counted(gctx):
    from jarvis import usage

    answer = types.GenerateContentResponse.model_validate({
        "candidates": [{"content": {"role": "model", "parts": [{"text": "Hello."}]}, "finish_reason": "STOP"}],
        "usage_metadata": {"prompt_token_count": 900, "candidates_token_count": 40, "thoughts_token_count": 60},
    })
    GeminiBrain(gctx, client=FakeGemini(answer)).chat("hi")
    assert usage.summary(gctx)["today"] == {"ai_calls": 1, "ai_tokens_in": 900, "ai_tokens_out": 100, "tts_chars": 0}


def test_gemini_reads_scanned_pdfs(gctx):
    from tests.test_files import make_pdf

    fake = FakeGemini(reply({"text": "A DEWA bill for 450 AED, due 5 October."}), reply({"text": "It's 450 AED."}))
    out = GeminiBrain(gctx, client=fake).chat("how much is this bill?", attachment=("bill.pdf", make_pdf(""), "application/pdf"))
    assert out.text == "It's 450 AED."
    look = fake.requests[0]["contents"]
    assert look[0]["inline_data"]["mime_type"] == "application/pdf" and "bill.pdf" in look[1]
    assert "DEWA bill for 450 AED" in str(fake.requests[1]["contents"][-1])
