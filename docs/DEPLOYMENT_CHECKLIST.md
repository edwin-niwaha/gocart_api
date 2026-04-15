# Deployment Checklist

## Before release
- [ ] Migrations generated and reviewed
- [ ] Automated tests green
- [ ] `python manage.py check --deploy` passes
- [ ] `python manage.py verify_environment --strict --check-services` passes
- [ ] Docker images build successfully
- [ ] `.env.staging` or production secrets updated
- [ ] Backups verified for the target database
- [ ] Release notes prepared

## Release window
- [ ] Pull latest images/code
- [ ] Run migrations
- [ ] Collect static files
- [ ] Restart web and worker services
- [ ] Check `/health/live/` and `/health/ready/`
- [ ] Validate login, tenant branding, product listing, checkout, and notifications

## After release
- [ ] Review application logs
- [ ] Review Celery worker logs
- [ ] Review payment callbacks or queued jobs
- [ ] Review Sentry or monitoring dashboard
- [ ] Notify stakeholders that release is complete
