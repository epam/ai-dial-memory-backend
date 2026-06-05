"""Skill instructions returned by the get_skill MCP tool."""

# ruff: noqa: E501
from __future__ import annotations

SKILL_INSTRUCTIONS: str = """\
# DIAL Memory

## Overview

You have two memory tools: **`store_memory`** for persisting facts and **`search_archive`** for recalling past events. Use them proactively — memory is only useful if you write to it.

## Core principle: write for retrieval

Before storing a memory, ask yourself: **"What future question will this answer?"** Each memory must be findable by a natural query the user might ask later. This drives two rules:

1. **Decompose** — if a message contains multiple distinct facts, store each as a separate memory. Each one should answer its own future question independently.
2. **Store what was asked** — when the user explicitly says "remember/note/store X", X must be stored. Do not substitute your own interpretation or summary of the surrounding context.
3. **Resolve dates** — always convert relative dates to absolute (e.g., "this Friday" → "Friday, June 5, 2026"). A memory read weeks later must still make sense.

## When to call `store_memory`

| Trigger | `memory_type` | Example |
|---------|---------------|---------|
| User states a permanent fact about themselves | `core` | "My name is Alex" |
| User establishes a preference | `core` | "Always generate code in Python" |
| User corrects a fact you stated | `core` | "Actually, I'm in Berlin, not London" |
| User explicitly asks you to remember | `core` | "Remember that I prefer dark mode" |
| Significant decision or workflow established this session | `episodic` | "We agreed to use Postgres for this project" |
| Bug root cause or non-obvious fix discovered | `episodic` | Resolved a tricky auth regression |

**Append-only**: never update or replace. If a fact changes, store the new version — both coexist and retrieval picks the contextually appropriate one.

## System-managed tools

`prime_memories` and `get_skill` are invoked automatically by the system at conversation start. Do **not** call them yourself — they are configured via hooks and handled by the runtime.

## When to call `search_archive`

Call it when the user references past events **not visible in the current context window**:
- "Last time we worked on this..."
- "Remember when we fixed that bug..."
- "What did we decide about X?"

Do **not** call it speculatively on every turn — only when past events are clearly referenced.

## Parameters

### `store_memory`

| Parameter | Type | Notes |
|-----------|------|-------|
| `content` | `str` | Clear, self-contained statement of the fact. Write as if injected cold into a future conversation. |
| `memory_type` | `"core"` or `"episodic"` | See table above. |
| `context` | `str` | Scope label. Use `"user"` for universal facts (core only). For **episodic** memories, ALWAYS set this to the deployment/app name — this is how `prime_memories` retrieves them. |
| `importance` | `float` 0.0–1.0 | See guide below. |

### `importance` guide

| Score | Meaning | Examples |
|-------|---------|---------|
| 0.9–1.0 | Universal — always injected regardless of topic | Name, spoken language, global code language preference |
| 0.7–0.9 | Project/context-specific — injected when relevant | Project stack, team conventions, recurring preferences per app |
| < 0.7 | Low-priority hints | One-off notes, soft preferences |

### `search_archive`

| Parameter | Type | Notes |
|-----------|------|-------|
| `query` | `str` | Natural-language description of what you're trying to recall. Be specific. |

## What NEVER to store

- Intermediate debug steps or speculative ideas
- General knowledge you already have (facts not specific to this user)
- File or document contents (that is RAG's job)
- Anything the user has not stated or agreed to — do not infer facts and store them as certain

## Examples

**User:** "I always write my docs in Markdown."
```
store_memory(
  content="User writes documentation in Markdown.",
  memory_type="core",
  context="user",
  importance=0.85
)
```

**User:** "Remember that project Orion uses a microservices architecture."
```
store_memory(
  content="Project Orion uses a microservices architecture.",
  memory_type="core",
  context="orion",
  importance=0.8
)
```

**User:** "What did we decide about the database last week?"
```
search_archive(query="database decision last week")
```

### Decomposition example

**User:** "On Friday June 5 I will demo this app to colleagues. Make a note that June 5 is Rubber Duckie Day."

WRONG — single memory that loses the explicit request:
```
store_memory(content="Demo scheduled: June 5, 2026, presenting app to colleagues.", ...)
```

RIGHT — two memories, each answering its own future question:
```
# Answers: "When is my demo?"
store_memory(
  content="App demo scheduled for Friday, June 5, 2026 — presenting to colleagues.",
  memory_type="episodic",
  context="app-name",
  importance=0.85
)

# Answers: "What should I mention to colleagues during the demo?"
store_memory(
  content="June 5 is Rubber Duckie in the Bath Day — a fun unofficial holiday. Mention to colleagues during the demo.",
  memory_type="episodic",
  context="app-name",
  importance=0.8
)
```
"""
