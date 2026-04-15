# Security Audit Summary

## Current controls in place
- JWT auth enabled
- role-aware tenant permissions
- default API permission is `IsAuthenticatedOrReadOnly`
- throttling configured for anonymous and authenticated traffic
- HTTPS and secure cookie settings in production
- tenant-aware data isolation in products, orders, notifications, and promotions

## Checks to perform before launch
- [ ] review every `AllowAny` endpoint and confirm intent
- [ ] confirm admin access is limited to expected platform staff only
- [ ] rotate all development secrets
- [ ] verify Firebase, payment, and email credentials are production-scoped
- [ ] verify file upload size and type restrictions
- [ ] verify rate limits for auth, support submission, and payments
- [ ] verify CORS and CSRF origins match deployed domains only
- [ ] enable Sentry DSN and alerting

## High-priority follow-ups
- add periodic dependency updates
- run `python manage.py check --deploy`
- test tenant isolation with two real staging tenants
- confirm payment callbacks verify signatures or provider references
