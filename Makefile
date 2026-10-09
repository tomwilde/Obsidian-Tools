SHELL := /bin/bash

.PHONY: help debug server-up logs tui down restart

help:
	@echo "Available targets:"
	@echo "  make debug      - build + start server (detached), then run interactive TUI"
	@echo "  make server-up  - build + start only the MCP server in background"
	@echo "  make logs       - tail MCP server logs"
	@echo "  make tui        - run only the interactive TUI client"
	@echo "  make down       - stop and remove compose services"
	@echo "  make restart    - down then debug"

debug: server-up
	docker compose run --rm --build tui

server-up:
	docker compose up -d --build server

logs:
	docker compose logs -f --tail=200 server

tui:
	docker compose run --rm --build tui

down:
	docker compose down

restart: down debug

