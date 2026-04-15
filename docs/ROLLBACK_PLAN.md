# Rollback Plan

## Trigger rollback when
- critical checkout failures occur
- login/token refresh fails broadly
- migrations corrupt tenant isolation
- workers cannot process critical jobs

## Rollback steps
1. Put the platform in maintenance mode for affected tenants if needed.
2. Switch traffic back to the previous stable container image.
3. Restart web and worker services with the previous release.
4. If a migration is backward-compatible, keep the DB and hotfix forward.
5. If a migration is not backward-compatible, restore from the latest verified backup.
6. Re-run smoke tests on the rolled-back version.

## Required assets before every release
- tagged release image
- tested database backup
- copy of previous `.env` values
- migration notes identifying reversible vs irreversible changes
