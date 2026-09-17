# ObsidianMCP

## Overview

A MCP server to expose an Obsidian vault - a folder tree of `md` files.

## Architecture

- Python FastApi/Flask server exposing the MCP protocol
- TUI app to provide a UI for the MCP (mainly for testing really)
- Readonly API for the first cut
- Capabilities:
  - Enumerate the filesystem
  - Read a file as text
  - RAG over MCP
    - Mark a folder for indexing
    - Query folder indexing status
    - Query under a folder using RAG
    - Clear all/some indexes

