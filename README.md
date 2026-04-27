# AI DIAL Memory MCP

A persistent memory service for AI assistants running on the [EPAM AI DIAL](https://epam-rail.com) platform.

## Overview

AI DIAL Memory MCP gives AI assistants the ability to remember information across conversations. It stores memories as vector embeddings, enabling semantic search so an assistant can retrieve relevant context from past interactions.

Memories are scoped per user and come in two types:

- **Core** — long-lived facts about the user or domain
- **Episodic** — context-specific moments from past conversations

The service is designed to be used alongside DIAL-hosted language models, enriching their responses with personalized, persistent context.
