.PHONY: up down build logs test unit-test clean ui-dev

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test: unit-test
	@echo "Running FIX integration test..."
	python tests/fix_client_simulator.py --host localhost --port 9876 --sender CLIENT1

unit-test:
	@echo "Running unit tests..."
	cd tests && pip install sortedcontainers pydantic --quiet && python -m pytest test_matching_engine.py -v

ui-dev:
	cd services/ui && npm install && npm run dev

clean:
	docker compose down -v --remove-orphans
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
