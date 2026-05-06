---
applyTo: "**/migrations/**"
---

# Migration Instructions

Files in `migrations/` are **🔴 Critical Path**. Extra care required.

## Mandatory Rules
- **Always auto-flag for @security review** when modifying migration files
- **Always require @validator** regardless of profile
- Every migration MUST be reversible (include down/rollback migration)
- Never delete or modify an already-applied migration — create a new one instead

## Safety Checks
- [ ] Has a rollback/down migration
- [ ] No data loss scenarios (check for DROP, TRUNCATE, column removal)
- [ ] No permission escalation (doesn't GRANT unexpected privileges)
- [ ] Runs within a transaction (where the DB supports it)
- [ ] Handles NULL values when adding NOT NULL columns (provide DEFAULT)
- [ ] Large table migrations won't lock the table for extended periods

## Testing
- Test both up AND down migrations
- Test with representative data (not just empty tables)
- Verify data integrity after migration round-trip (up → down → up)

## Naming
- Use timestamped naming: `YYYYMMDDHHMMSS_descriptive_name`
- Be descriptive: `add_user_email_index` not `update_users`
