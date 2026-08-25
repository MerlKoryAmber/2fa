.PHONY: verify test test-bot lint up down rebuild install update uninstall

verify: test lint

test:
	podman run --rm \
	  -v "$(CURDIR)/tests:/tests:Z" \
	  -w /app \
	  --env-file .env \
	  -e SEED_ON_STARTUP=false \
	  -e PYTHONPATH=/app \
	  --entrypoint pytest \
	  localhost/mk2fa-api:latest \
	  /tests -q

lint:
	cd api && python3 -m compileall -q app
	python3 -m compileall -q express-bot/app

test-bot:
	cd express-bot && PYTHONPATH=. python3 -m pytest tests -q

up:
	PYTHONPATH=/usr/local/lib/python3.9/site-packages podman-compose up --build -d

down:
	podman-compose down

rebuild:
	podman-compose up --build -d --force-recreate api worker worker-otp web radius

install:
	./scripts/install.sh --skip-pkgs

update:
	./scripts/update.sh

uninstall:
	./scripts/uninstall.sh
