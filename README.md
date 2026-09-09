## Configuration Development Environment

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Install Dependencies (creates `.venv` and installs base + dev group):**
   ```bash
   uv sync
   ```

3. **Activate Env**
   ```bash
   source .venv/bin/activate
   ```

4. **Run Migrations**
   ```bash
   uv run python manage.py migrate
   ```

5. **Create Super User**
   ```bash
   uv run python manage.py createsuperuser
   ```

6. **Run Server**
   ```bash
   uv run python manage.py runserver
   ```

7. **Start Tailwind (Development)**
   ```bash
   uv run python manage.py tailwind start
   ```

## Docker

The project is containerized with lightweight multi-stage images
(Python runtime without Node; Tailwind CSS is compiled at build time).

### Development

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Start the stack** (postgres, redis, mailpit, django, celery, celerybeat):
   ```bash
   docker compose up --build
   ```

   - App: http://localhost:8000
   - Mailpit UI: http://localhost:8025

3. **Create Super User**
   ```bash
   docker compose exec django python manage.py createsuperuser
   ```

4. **Get Location Information**
   ```bash
   docker compose exec django python manage.py loaddata apps/core/fixtures/ubigeo_data.json
   ```

### Production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The production image excludes the `dev` dependency group (linters, testing,
debug tools). Mailpit is optional in production and can be disabled with
`--profile mailpit` (it only runs when explicitly enabled).

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile mailpit up -d
```

### Convenience commands

```bash
make dev        # docker compose up --build
make prod       # production stack (up -d --build)
make down       # docker compose down
make logs       # docker compose logs -f
make ps         # docker compose ps
```

## Production

Install base + production group (without dev tools):

```bash
uv sync --no-dev --group production
```

## Location Information

1. **Get Location Information**
```bash
   uv run python manage.py loaddata apps/core/fixtures/ubigeo_data.json
```

## Coverage

1. **Run Tests with coverage**
   ```bash
   uv run coverage run manage.py test --settings=config.settings.testing
   ```

2. **Generate report**
   ```bash
   uv run coverage report --sort=cover
   ```

3. **Generate HTML report**
   ```bash
   uv run coverage html
   ```

## Linting

1. **Install pre-commit hooks** (included in the `dev` group)
```bash
   uv run pre-commit install
```

2. **Run pre-commit hooks**
```bash
   uv run pre-commit run --all-files
```

## Translations

1. **Generate translation files**
```bash
   uv run python manage.py makemessages -l es --ignore ".venv/*"
```

2. **Compile translation files**
```bash
   uv run python manage.py compilemessages -l es --ignore ".venv/*"
```