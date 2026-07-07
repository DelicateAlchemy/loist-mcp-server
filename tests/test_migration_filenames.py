"""
Guard test for database migration filenames.

Pure filesystem check - requires no database connectivity, so it runs under the
default `unit` marker (see root conftest.py: only files explicitly listed there are
marked `requires_db`/`requires_gcs`, and this file is not one of them).

This exists because of LOI-51: three migration files historically shared the same
"002_" numeric prefix, which is invalid for a migration runner that applies files in
lexicographic filename order (the ordering across files sharing a prefix is
underspecified/accidental). This test prevents the same mistake from being
reintroduced.
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

MIGRATIONS_DIR = Path(__file__).parent.parent / "database" / "migrations"

# Matches the leading numeric prefix of a migration filename, e.g. "014" in
# "014_add_user_id.sql".
PREFIX_PATTERN = re.compile(r"^(\d+)_")


def _numeric_prefixes() -> Dict[str, List[str]]:
    """Map each numeric prefix found in database/migrations/ to the filenames using it."""
    prefixes: Dict[str, List[str]] = defaultdict(list)
    for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = PREFIX_PATTERN.match(migration_file.name)
        if match:
            prefixes[match.group(1)].append(migration_file.name)
    return prefixes


class TestMigrationFilenamePrefixes:
    """Guard against duplicate numeric prefixes in database/migrations/."""

    def test_migrations_directory_exists(self) -> None:
        assert MIGRATIONS_DIR.is_dir(), f"Expected migrations directory at {MIGRATIONS_DIR}"

    def test_no_duplicate_numeric_prefixes(self) -> None:
        """Every migration file's leading numeric prefix must be unique.

        The migration runner (database/migrate.py) applies files in lexicographic
        filename order. If two files share the same numeric prefix, the order between
        them is decided only by the rest of the filename, which is fragile and easy
        to get wrong (this happened for "002_" - see database/migrations/README.md).
        """
        prefixes = _numeric_prefixes()
        duplicates = {prefix: names for prefix, names in prefixes.items() if len(names) > 1}

        assert not duplicates, (
            "Duplicate migration numeric prefixes found (each prefix must be unique): "
            f"{duplicates}"
        )

    def test_all_migration_files_have_numeric_prefix(self) -> None:
        """Every .sql file in database/migrations/ must start with digits + underscore."""
        unprefixed = [
            migration_file.name
            for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql"))
            if not PREFIX_PATTERN.match(migration_file.name)
        ]

        assert not unprefixed, (
            "Migration files must start with a numeric prefix (e.g. '016_'): " f"{unprefixed}"
        )

    def test_at_least_expected_migrations_present(self) -> None:
        """Sanity check that we're pointed at the real migrations directory."""
        migration_files = list(MIGRATIONS_DIR.glob("*.sql"))
        assert len(migration_files) >= 15, (
            "Expected at least 15 migration files (001-015 after the LOI-51 dedupe), "
            f"found {len(migration_files)}"
        )
