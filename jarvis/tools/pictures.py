"""Making pictures with Google's image model (uses GEMINI_API_KEY)."""

from __future__ import annotations

from jarvis.tools import Context, ToolError, tool


@tool(
    "generate_image",
    "Create a picture from a description (posters, logos, illustrations, photos of imagined scenes), "
    "or edit the most recent picture (one you made, or a photo the user just sent) with edit_last. "
    "The picture is shown to the user automatically; just say a line about it. Each one costs a few cents.",
    {
        "prompt": {"type": "string", "description": "A detailed description: subject, style, colours, text to include."},
        "edit_last": {"type": "boolean", "description": "Change the most recent picture instead of starting fresh."},
    },
    ["prompt"],
    needs_gemini=True,
)
def generate_image(ctx: Context, args: dict) -> str:
    from jarvis import google_ai, images, usage

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        raise ToolError("Describe the picture first.")
    source = images.last(ctx) if args.get("edit_last") else None
    if args.get("edit_last") and not source:
        raise ToolError("There's no recent picture to edit. Describe a new one instead.")
    try:
        data, mime, note = google_ai.generate_image(ctx.settings, prompt, source)
    except google_ai.AIUnavailable as exc:
        raise ToolError(str(exc)) from exc
    try:
        image_id = images.save(ctx, prompt, data, mime)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    usage.record(ctx, {"images": 1})
    return f"Picture #{image_id} is ready and on the user's screen." + (f" (Model's note: {note[:200]})" if note else "")
