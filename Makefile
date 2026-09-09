.PHONY: dev dev-build prod prod-build down logs ps

dev:
	docker compose up --build

dev-build:
	docker compose build

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-build:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps