# Weibo Search Crawler Example Makefile
# Usage: make <target>

.PHONY: help install dev clean worker-all worker-cookie worker-search search fill-pool redis-start dashboard

help:
	@echo "Weibo Search Crawler Example"
	@echo ""
	@echo "Setup:"
	@echo "  make install        - Install dependencies"
	@echo ""
	@echo "Workers:"
	@echo "  make worker-all     - Start all workers"
	@echo "  make worker-cookie  - Start cookie worker"
	@echo "  make worker-search  - Start search worker"
	@echo "  make fill-pool      - Fill cookie pool (1 cookie)"
	@echo ""
	@echo "Search:"
	@echo "  make search KEYWORD=\"keyword\" - Test search"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make redis-start    - Start Redis (Docker)"
	@echo "  make dashboard      - Start RQ Dashboard"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Clean artifacts"

# Setup
install:
	uv sync

# Workers
worker-all:
	uv run weibo-worker all

worker-cookie:
	uv run weibo-worker cookie

worker-search:
	uv run weibo-worker search

fill-pool:
	uv run weibo-worker fill-pool --count 1

# Search
KEYWORD ?= "test"
PAGES ?= 5
search:
	uv run weibo-search search $(KEYWORD) --pages $(PAGES) --direct

# Infrastructure
redis-start:
	@docker run -d --name weibo-redis -p 6379:6379 redis:7-alpine || docker start weibo-redis

dashboard:
	uv run rq-dashboard

# Cleanup
clean:
	rm -rf dist *.egg-info .pytest_cache logs/*.jsonl
	find . -type d -name "__pycache__" -exec rm -rf {} +
