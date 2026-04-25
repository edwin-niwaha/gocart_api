# GoCart API

[![Django CI](https://github.com/edwin-niwaha/gocart_api/actions/workflows/ci.yml/badge.svg)](https://github.com/edwin-niwaha/gocart_api/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/django-6.0.3-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.16.1-A30000?logo=django&logoColor=white)
![Celery](https://img.shields.io/badge/celery-5.6.2-37814A?logo=celery&logoColor=white)
![Multi-tenant](https://img.shields.io/badge/architecture-multi--tenant-0A7EA4)
![License](https://img.shields.io/badge/license-GPLv3-blue.svg)

Tenant-aware ecommerce backend for GoCart, built with Django, Django REST Framework, Celery, JWT authentication, and operational integrations for payments, notifications, media, and tenant configuration.

## Overview

GoCart API powers a multi-tenant commerce platform with support for:

- tenant-scoped catalog, carts, orders, addresses, reviews, and wishlists
- guest and authenticated checkout flows
- coupon and shipping-aware totals
- MTN Mobile Money payment workflows plus cash-on-delivery support
- push notifications, support messaging, newsletters, and audit logs
- tenant branding, memberships, settings, and feature flags
- admin dashboard analytics and health checks

## Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.12 |
| Framework | Django 6.0.3 |
| API | Django REST Framework 3.16.1 |
| Auth | SimpleJWT, dj-rest-auth, django-allauth |
| Async jobs | Celery 5.6.2 |
| Broker / result backend | Redis |
| Database | SQLite by default, PostgreSQL in Docker / production |
| Media | Cloudinary |
| Notifications | Firebase Admin |
| Payments | MTN Mobile Money integrations |

## Key Features

- Multi-tenant request resolution using the `X-Tenant-Slug` header
- Product catalog with categories, variants, pricing, and stock tracking
- Cart isolation and guest cart support
- Order checkout with idempotency, stock validation, shipping, and coupon application
- Payment finalization safeguards to prevent mismatched totals or cross-tenant access
- Tenant-level branding, settings, memberships, and feature flags
- Device token registration and tenant-scoped notification delivery
- Support message and newsletter workflows backed by Celery tasks
- Health endpoints for liveness and readiness

## Quick Start

### Local development

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

The default local configuration uses SQLite. If you want PostgreSQL and Redis locally, update `.env` and run the supporting services yourself or use Docker Compose.

### Run the Celery worker

Windows PowerShell:

```powershell
celery -A core worker -l info -P solo
```

macOS / Linux:

```bash
export DJANGO_SETTINGS_MODULE=core.settings.development
celery -A core worker -l info
```

## Docker

The repository includes a Dockerfile and `docker-compose.yml` for the API, worker, PostgreSQL, and Redis.

```bash
docker compose up --build
```

Notes:

- the container entrypoint runs `migrate` and `collectstatic` automatically
- Docker Compose exposes the API on `http://localhost:8000`
- PostgreSQL 16 and Redis 7 are provisioned as companion services

## Environment Configuration

Start from `.env.example` for development or `.env.production.example` for production.

Important settings include:

- `SECRET_KEY` and `JWT_SECRET_KEY`
- `DATABASE_URL`
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`
- `ENABLE_EMAIL`
- `ENABLE_FIREBASE`
- `ENABLE_MOMO`
- `ENABLE_CLOUDINARY`
- `ENABLED_CHECKOUT_PAYMENT_METHODS`
- `TIME_ZONE`

## Tenant-Aware Requests

Most API operations are tenant-scoped. Pass the active tenant slug in the request header:

```http
X-Tenant-Slug: tenant-a
```

Example:

```bash
curl http://127.0.0.1:8000/api/v1/products/ \
  -H "X-Tenant-Slug: tenant-a"
```

## Useful Endpoints

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/tenants/current/`
- `GET /api/v1/products/`
- `POST /api/v1/cart-items/`
- `POST /api/v1/orders/checkout/`
- `POST /api/v1/payments/mtn/initiate/`
- `POST /api/v1/notifications/broadcast/`
- `GET /api/v1/admin/dashboard/summary/`

## Testing

Run the test suite with the dedicated testing settings module:

```bash
python manage.py test --settings=core.settings.testing -v 2
```

Current suite size in this repository: 70 tests.

## Project Layout

```text
gocart_api/
|-- api/                # API route aggregation
|-- apps/               # Domain apps: products, orders, payments, tenants, etc.
|-- core/               # Settings, middleware, celery, health, exceptions
|-- templates/          # Email and template assets
|-- docker-compose.yml  # Local service orchestration
|-- Dockerfile          # API image definition
`-- manage.py
```

## Production Notes

- Use `core.settings.production` and `.env.production.example` as the baseline.
- Serve the app with Gunicorn:

```bash
gunicorn core.wsgi:application --config gunicorn.conf.py
```

- Run a separate Celery worker for background jobs.
- Back the app with PostgreSQL and Redis in production.
- Enable Firebase, Cloudinary, email, and mobile money only when the required credentials are configured.

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
