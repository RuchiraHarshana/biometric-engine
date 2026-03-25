"""Deprecated migration script.

This repository has migrated to Supabase. The original migration tool that copied
rows from a local SQLAlchemy DB into Supabase is deprecated and removed to avoid
introducing runtime SQLAlchemy imports in the production code path.

If you still need to migrate an old local DB, keep a copy of the original
`scripts/migrate_local_to_supabase.py` from your Git history and run it before
removing SQLAlchemy files. This file intentionally no-ops to avoid import errors.
"""

if __name__ == "__main__":
    print("migrate_local_to_supabase.py is deprecated. Use your saved migration script if needed.")
