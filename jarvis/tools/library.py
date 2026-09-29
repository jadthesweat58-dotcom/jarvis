"""The library: documents the user has shared, searchable later."""

from __future__ import annotations

from jarvis.tools import Context, ToolError, tool


@tool(
    "search_library",
    "Search the user's library of saved documents (files they attached, pages they saved) and "
    "return the most relevant passages. Use it whenever they ask about a document, contract, "
    "receipt, report or article they shared before.",
    {"query": {"type": "string", "description": "What to look for, as a question or keywords."}},
    ["query"],
)
def search_library(ctx: Context, args: dict) -> str:
    from jarvis import library

    hits = library.search(ctx, str(args.get("query", "")))
    if not hits:
        return "Nothing in the library matches that."
    return "\n\n".join(f"[#{h['doc_id']} {h['name']}, passage {h['idx'] + 1}]\n{h['text']}" for h in hits)


@tool("list_library", "List the documents saved in the user's library.")
def list_library(ctx: Context, args: dict) -> str:
    from jarvis import library

    docs = library.documents(ctx)
    if not docs:
        return "The library is empty. Files the user attaches are saved there automatically."
    return "\n".join(f"#{d['id']} {d['name']} ({d['chars']:,} characters, {d['created_at'][:10]})" for d in docs)


@tool("forget_document", "Remove a document from the library by id.", {"id": {"type": "integer"}}, ["id"])
def forget_document(ctx: Context, args: dict) -> str:
    from jarvis import library

    if not library.forget(ctx, int(args["id"])):
        raise ToolError(f"No document #{args['id']} in the library.")
    return f"Removed document #{args['id']} from the library."


@tool(
    "save_webpage",
    "Save a web page or online PDF to the user's library so it can be searched later.",
    {"url": {"type": "string"}, "title": {"type": "string", "description": "Optional name for it."}},
    ["url"],
)
def save_webpage(ctx: Context, args: dict) -> str:
    from jarvis import library
    from jarvis.tools.extras import fetch_page

    final, title, text = fetch_page(str(args["url"]))
    if not text.strip():
        raise ToolError("That page has no readable text to save.")
    name = (args.get("title") or title or final)[:200]
    doc_id = library.add_document(ctx, name, text, source=final)
    return f"Saved \"{name}\" to the library as document #{doc_id}."
