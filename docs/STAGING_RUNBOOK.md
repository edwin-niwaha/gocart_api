# Staging Runbook

## 1. Prepare environment
- Copy `.env.production.example` to `.env.staging`.
- Set `ENVIRONMENT=production`.
- Point `DATABASE_URL` to the staging Postgres instance.
- Point `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` to staging Redis.
- Set `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` to staging domains.
- Set `ENABLE_FIREBASE`, `ENABLE_MOMO`, `ENABLE_CLOUDINARY` only when credentials are ready.

## 2. Verify configuration
```bash
python manage.py verify_environment --strict --check-services --settings=core.settings.production
python manage.py check --deploy --settings=core.settings.production
```

## 3. Build and start
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build -d
```

## 4. Apply release steps
```bash
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py collectstatic --noinput
```

## 5. Smoke test
- `GET /health/live/`
- `GET /health/ready/`
- login
- tenant config
- create/update a product as tenant admin
- checkout flow in staging
- worker task execution

## 6. Sign-off
- Confirm no 5xx responses in logs.
- Confirm Sentry or error monitoring is receiving events.
- Confirm Celery worker is processing queued jobs.
