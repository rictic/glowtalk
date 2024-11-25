Generic single-database configuration.

```bash
# Generate a new migration, after updating model.
alembic revision --autogenerate -m "Add character voices"

# Apply the migration to your database
alembic upgrade head

# See current database version
alembic current

# Roll back one migration
alembic downgrade -1

# See migration history
alembic history

# Generate a migration without auto-detection (if you need more control)
alembic revision -m "Custom migration"
```
