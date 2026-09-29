"""Jarvis's brain running on Google Gemini.

Same behaviour as the Claude brain in jarvis/brain.py (tools, approvals,
memory, saved history); only the conversation format and API differ.

Gemini 3 models attach "thought signatures" to their tool calls. They must be
sent back unchanged on the next request, so the model's replies are stored
exactly as returned (the SDK round-trips the signatures through JSON).
"""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from jarvis.brain import AI_TIMEOUT, MAX_HISTORY_MESSAGES, MAX_TOOL_ROUNDS, VISION_PROMPT, Brain, Reply
from jarvis.tools import Context, Tool

log = logging.getLogger("jarvis.gemini")

THINKING_LEVELS = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH", "xhigh": "HIGH", "max": "HIGH"}
BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


class GeminiBrain(Brain):
    def __init__(self, ctx: Context, **kwargs: Any):
        super().__init__(ctx, **kwargs)
        if self.web_search:
            self.tools = [*self.tools, self._web_search_tool()]
            self.tool_map = {t.name: t for t in self.tools}

    # --- API ---------------------------------------------------------------------
    def _client(self):
        if self.client is None:
            if not self.settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file "
                                   "(or your cloud host's environment settings).")
            self.client = genai.Client(api_key=self.settings.gemini_api_key,
                                       http_options=types.HttpOptions(timeout=AI_TIMEOUT * 1000))
        return self.client

    def _config(self) -> types.GenerateContentConfig:
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema={"type": "object", "properties": t.parameters, "required": t.required},
            )
            for t in self.tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            # Jarvis runs the tools itself, so it can ask for approval first.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        if self.settings.model.startswith("gemini-3"):
            level = THINKING_LEVELS.get(self.effort, "MEDIUM")
            config.thinking_config = types.ThinkingConfig(thinking_level=level)
        return config

    def _request(self) -> types.GenerateContentResponse:
        contents = [types.Content.model_validate(m) for m in self.messages]
        response = self._client().models.generate_content(
            model=self.settings.model, contents=contents, config=self._config()
        )
        self._count_usage(response)
        return response

    def _count_usage(self, response: Any) -> None:
        u = getattr(response, "usage_metadata", None)
        tokens_out = (int(getattr(u, "candidates_token_count", 0) or 0)
                      + int(getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        self._add_usage(1, int(getattr(u, "prompt_token_count", 0) or 0) if u else 0, tokens_out)

    def describe_image(self, data: bytes, mime: str, question: str, prompt: str | None = None) -> str:
        """What the AI sees in a picture (or a PDF's pages)."""
        config = types.GenerateContentConfig()
        if self.settings.model.startswith("gemini-3"):
            config.thinking_config = types.ThinkingConfig(thinking_level="LOW")
        response = self._client().models.generate_content(
            model=self.settings.model,
            contents=[types.Part.from_bytes(data=data, mime_type=mime),
                      prompt or VISION_PROMPT.format(question=question[:500])],
            config=config,
        )
        self._count_usage(response)
        return (response.text or "").strip() or "I couldn't make out that picture."

    # --- conversation ----------------------------------------------------------------
    def _user_turn(self, text: str) -> dict:
        return {"role": "user", "parts": [{"text": t} for t in self._user_texts(text)]}

    def _chat(self, text: str) -> Reply:
        if len(self.messages) > MAX_HISTORY_MESSAGES:
            self.messages = []  # start fresh rather than editing history; facts carry over
        checkpoint = len(self.messages)
        self.messages.append(self._user_turn(text))
        actions: list[dict] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = self._request()
                candidate = response.candidates[0] if response.candidates else None
                parts = (candidate.content.parts if candidate and candidate.content else None) or []
                if not parts:
                    # Nothing usable came back: blocked by safety filters or a malformed reply.
                    del self.messages[checkpoint:]
                    reason = str(getattr(candidate, "finish_reason", "") or "").split(".")[-1]
                    if reason in BLOCKED or getattr(response.prompt_feedback, "block_reason", None):
                        return Reply("I'm afraid I can't help with that one.", actions)
                    return Reply("Sorry, I lost my train of thought there. Could you say that again?", actions)
                content = types.Content(role="model", parts=parts)
                self.messages.append(content.model_dump(mode="json", exclude_none=True))
                calls = [p.function_call for p in parts if p.function_call]
                if not calls:
                    self._save()
                    text_out = "\n".join(p.text for p in parts if p.text and not p.thought).strip()
                    return Reply(text_out or "Done.", actions)
                results = []
                for call in calls:
                    output, is_error = self._execute_tool(call.name, dict(call.args or {}), actions)
                    results.append({"function_response": {
                        "id": call.id,
                        "name": call.name,
                        "response": {"error": output} if is_error else {"result": output},
                    }})
                self.messages.append({"role": "user", "parts": results})
            self._save()
            return Reply("I've been going round in circles on that one; could you rephrase?", actions)
        except Exception:
            del self.messages[checkpoint:]  # a failed turn must not corrupt the history
            raise

    # --- web search --------------------------------------------------------------------
    def _web_search_tool(self) -> Tool:
        def search(ctx: Context, args: dict) -> str:
            query = str(args.get("query", "")).strip()
            if not query:
                return "Give a search query."
            where = f" The user is in {self.settings.home_city}." if self.settings.home_city else ""
            response = self._client().models.generate_content(
                model=self.settings.model,
                contents=f"Search the web and answer with the key facts, figures and dates: {query}{where}",
                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
            )
            self._count_usage(response)
            answer = (response.text or "").strip() or "No results found."
            sources = []
            meta = response.candidates[0].grounding_metadata if response.candidates else None
            for chunk in (meta.grounding_chunks if meta and meta.grounding_chunks else [])[:5]:
                if chunk.web and chunk.web.title:
                    sources.append(chunk.web.title)
            return answer + (f"\n\nSources: {', '.join(sources)}" if sources else "")

        return Tool(
            name="web_search",
            description="Search the web (Google) for current information: news, facts, prices, "
                        "opening hours, sports, anything recent. Returns a short answer with sources.",
            parameters={"query": {"type": "string", "description": "What to look up."}},
            required=["query"],
            handler=search,
        )
