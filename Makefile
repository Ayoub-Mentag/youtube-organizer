# CSV file inside ./data. Override with: make up CSV="other.csv"
CSV ?= watch-later-videos.csv

.PHONY: help up check build fetch classify push-preview push reset

help:
	@echo "make up            run everything: fetch -> classify -> push (safe to re-run, it resumes)"
	@echo "make fetch         Phase 1: CSV -> data/videos.json"
	@echo "make classify      Phase 2: videos.json -> data/categories.json (needs the Ollama app running)"
	@echo "make push-preview  Phase 3: show what would be created on YouTube (changes nothing)"
	@echo "make push          Phase 3: create the playlists and add the videos"
	@echo "make reset         delete videos.json and categories.json (starts over)"

up: check build fetch classify push

check:
	@test -f .env || (echo "Missing .env. Run: cp .env.example .env  and add your YouTube API key." && exit 1)
	@! grep -q paste_your_key_here .env || (echo "Edit .env and replace paste_your_key_here with your API key." && exit 1)
	@test -f "data/$(CSV)" || (echo "Missing data/$(CSV). Export Watch Later from Google Takeout (see README)." && exit 1)
	@test -f data/client_secret.json || (echo "Missing data/client_secret.json. Create an OAuth Desktop client (see README)." && exit 1)
	@curl -sf http://localhost:11434 > /dev/null || (echo "Ollama is not running. Start the Ollama app (see README)." && exit 1)

build:
	docker compose build

fetch:
	docker compose run --rm fetch "$(CSV)"

classify:
	docker compose run --rm classify

push-preview:
	docker compose run --rm push --dry-run

push:
	docker compose run --rm --service-ports push

reset:
	rm -f data/videos.json data/categories.json