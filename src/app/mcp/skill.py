"""Skill instructions returned by the get_skill MCP tool."""

# ruff: noqa: E501
from __future__ import annotations

SKILL_INSTRUCTIONS: str = """\
# DIAL Memory

## Overview

You have two memory tools: **`store_memory`** for persisting facts and **`search_archive`** for recalling past events. Use them proactively — memory is only useful if you write to it.

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

## When to call `prime_memories`

Call it **once, at the start of every dialogue**, as a synthetic tool call. It loads:
- All top core memories (user preferences, permanent facts) ordered by importance
- Episodic memories scoped to the current app/deployment name

Do **not** call it mid-conversation — it is a context-priming tool, not a search tool.

### `prime_memories`

| Parameter | Type | Notes |
|-----------|------|-------|
| `app_name` | `str | None` | The deployment or application name. Pass the name of the current DIAL deployment. When `None`, only core memories are returned. |

## When to call `get_skill`

Call it **once, at the start of every dialogue**, as a synthetic tool call, to load these instructions into context.

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
"""
