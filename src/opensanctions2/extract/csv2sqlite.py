
import sqlite3
import duckdb
from pathlib import Path
from opensanctions2.config import (
    OUTPUT_DIR,
    STATEMENTS_CSV_PATH,
    STATEMENTS_FILTERED_DB_PATH,
    TEMP_STATEMENTS_FILTERED_DB_PATH,
    STATEMENTS_FULL_DB_PATH,
    TEMP_STATEMENTS_FULL_DB_PATH,
    TARGETS_CSV_PATH,
    TARGETS_DB_PATH,
    TEMP_TARGETS_DB_PATH,
)


# ==================================================
# 1. CONFIGURATION
# ==================================================

BATCH_SIZE = 10_000

DUCKDB_MEMORY_LIMIT = "4GB"

DUCKDB_THREADS = 4


# ==================================================
# 2. EXTRACTION CRITERIA
# ==================================================

TARGET_SCHEMA = "Person"

TARGET_PROP = "topics"

TARGET_VALUES = (
    "sanction",
    "sanction.counter",
)


# ==================================================
# 3. HELPERS
# ==================================================

def sql_literal(value: str) -> str:
    """Escape a string for use as a SQL literal."""
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    """Quote a SQL identifier."""
    return '"' + value.replace('"', '""') + '"'


# ==================================================
# 4. EXTRACTION
# ==================================================

def extract_statements() -> int:
    """
    Extract all Person statements belonging to individuals
    identified by at least one matching sanction topic.

    Individual selection criteria:
        schema = Person
        prop = topics
        value IN (sanction, sanction.counter)

    All Person statements associated with the selected
    canonical IDs are transferred to SQLite.

    Returns:
        Number of extracted statement records.
    """

    if not STATEMENTS_CSV_PATH.is_file():
        raise FileNotFoundError(
            f"Input CSV not found: {STATEMENTS_CSV_PATH}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Remove an incomplete temporary database
    if TEMP_STATEMENTS_FILTERED_DB_PATH.exists():
        TEMP_STATEMENTS_FILTERED_DB_PATH.unlink()

    total_inserted = 0

    try:

        # ------------------------------------------
        # DuckDB: CSV reading and filtering
        # ------------------------------------------

        print("Initializing DuckDB for statements.csv...")

        with duckdb.connect() as duck:

            duck.execute(
                f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'"
            )

            duck.execute(
                f"SET threads = {DUCKDB_THREADS}"
            )

            duck.execute(
                f"SET temp_directory = "
                f"{sql_literal(str(OUTPUT_DIR / 'duckdb_temp'))}"
            )

            csv_path = sql_literal(str(STATEMENTS_CSV_PATH))

            values_sql = ", ".join(
                sql_literal(value)
                for value in TARGET_VALUES
            )

            query = f"""
                WITH sanctioned_individuals AS MATERIALIZED (

                    SELECT DISTINCT canonical_id

                    FROM read_csv_auto(
                        {csv_path},
                        header = true,
                        all_varchar = true,
                        parallel = false
                    )

                    WHERE "schema" = {sql_literal(TARGET_SCHEMA)}
                      AND prop = {sql_literal(TARGET_PROP)}
                      AND value IN ({values_sql})
                )

                SELECT source.*

                FROM read_csv_auto(
                    {csv_path},
                    header = true,
                    all_varchar = true,
                    parallel = false
                ) AS source

                INNER JOIN sanctioned_individuals AS selected
                    USING (canonical_id)

                WHERE source."schema" = {sql_literal(TARGET_SCHEMA)}
            """

            print("Executing extraction query...")

            cursor = duck.execute(query)

            # Retrieve source column names
            columns = [
                description[0]
                for description in cursor.description
            ]

            # --------------------------------------
            # SQLite: database and table creation
            # --------------------------------------

            print("Initializing SQLite...")

            with sqlite3.connect(TEMP_STATEMENTS_FILTERED_DB_PATH) as sqlite:

                sqlite.execute(
                    "PRAGMA synchronous = NORMAL"
                )

                # Create table using original CSV columns
                column_definitions = ", ".join(
                    f"{sql_identifier(column)} TEXT"
                    for column in columns
                )

                sqlite.execute(
                    f"""
                    CREATE TABLE statements (
                        {column_definitions}
                    )
                    """
                )

                placeholders = ", ".join(
                    ["?"] * len(columns)
                )

                insert_query = (
                    f"INSERT INTO statements VALUES "
                    f"({placeholders})"
                )

                # ----------------------------------
                # Batch transfer
                # ----------------------------------

                print("Transferring records to SQLite...")

                while True:

                    batch = cursor.fetchmany(BATCH_SIZE)

                    if not batch:
                        break

                    sqlite.executemany(
                        insert_query,
                        batch
                    )

                    total_inserted += len(batch)

                    print(
                        f"\rInserted: {total_inserted:,}",
                        end="",
                        flush=True
                    )

                print()

                # ----------------------------------
                # Index creation
                # ----------------------------------

                if "entity_id" in columns:

                    sqlite.execute("""
                        CREATE INDEX idx_statements_entity
                        ON statements(entity_id)
                    """)

                if "canonical_id" in columns:

                    sqlite.execute("""
                        CREATE INDEX idx_statements_canonical
                        ON statements(canonical_id)
                    """)

        # ------------------------------------------
        # Finalize database
        # ------------------------------------------

        TEMP_STATEMENTS_FILTERED_DB_PATH.replace(STATEMENTS_FILTERED_DB_PATH)


        print("\nExtraction completed successfully.")
        print(f"Total statements: {total_inserted:,}")
        print(f"SQLite database: {STATEMENTS_FILTERED_DB_PATH}")
        print(f"SQLite table: statements")

        return total_inserted

    except Exception:

        if TEMP_STATEMENTS_FILTERED_DB_PATH.exists():
            TEMP_STATEMENTS_FILTERED_DB_PATH.unlink()

        raise



def extract_unfiltered_csv(
    csv_path: Path,
    db_path: Path,
    temp_db_path: Path,
    table_name: str,
) -> int:
    """
    Transfer all records from a CSV file to SQLite using DuckDB.

    No filtering is applied.

    All source columns are stored as TEXT.

    Args:
        csv_path: Input CSV path.
        db_path: Final SQLite database path.
        temp_db_path: Temporary SQLite database path.
        table_name: Name of the SQLite table.

    Returns:
        Number of extracted records.
    """

    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Input CSV not found: {csv_path}"
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove an incomplete temporary database
    if temp_db_path.exists():
        temp_db_path.unlink()

    total_inserted = 0

    try:

        # ------------------------------------------
        # DuckDB: CSV reading
        # ------------------------------------------

        print(f"\nInitializing DuckDB for {csv_path.name}...")

        with duckdb.connect() as duck:

            duck.execute(
                f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'"
            )

            duck.execute(
                f"SET threads = {DUCKDB_THREADS}"
            )

            duck_temp_dir = db_path.parent / "duckdb_temp"
            duck_temp_dir.mkdir(parents=True, exist_ok=True)

            duck.execute(
                f"SET temp_directory = "
                f"{sql_literal(str(duck_temp_dir))}"
            )

            query = f"""
                SELECT *

                FROM read_csv_auto(
                    {sql_literal(str(csv_path))},
                    header = true,
                    all_varchar = true,
                    parallel = false
                )
            """

            print("Executing extraction query...")

            cursor = duck.execute(query)

            columns = [
                description[0]
                for description in cursor.description
            ]

            # --------------------------------------
            # SQLite: database and table creation
            # --------------------------------------

            print("Initializing SQLite...")

            with sqlite3.connect(temp_db_path) as sqlite:

                sqlite.execute(
                    "PRAGMA synchronous = NORMAL"
                )

                column_definitions = ", ".join(
                    f"{sql_identifier(column)} TEXT"
                    for column in columns
                )

                sqlite.execute(
                    f"""
                    CREATE TABLE {sql_identifier(table_name)} (
                        {column_definitions}
                    )
                    """
                )

                placeholders = ", ".join(
                    ["?"] * len(columns)
                )

                insert_query = (
                    f"INSERT INTO {sql_identifier(table_name)} "
                    f"VALUES ({placeholders})"
                )

                # ----------------------------------
                # Batch transfer
                # ----------------------------------

                print("Transferring records to SQLite...")

                while True:

                    batch = cursor.fetchmany(BATCH_SIZE)

                    if not batch:
                        break

                    sqlite.executemany(
                        insert_query,
                        batch
                    )

                    total_inserted += len(batch)

                    print(
                        f"\rInserted: {total_inserted:,}",
                        end="",
                        flush=True
                    )

                print()

        # ------------------------------------------
        # Finalize database
        # ------------------------------------------

        temp_db_path.replace(db_path)

        print("\nExtraction completed successfully.")
        print(f"Source: {csv_path}")
        print(f"Total records: {total_inserted:,}")
        print(f"SQLite database: {db_path}")
        print(f"SQLite table: {table_name}")

        return total_inserted

    except Exception:

        if temp_db_path.exists():
            temp_db_path.unlink()

        raise




def extract_unfiltered_datasets() -> tuple[int, int]:

    statements_count = extract_unfiltered_csv(
        csv_path=STATEMENTS_CSV_PATH,
        db_path=STATEMENTS_FULL_DB_PATH,
        temp_db_path=TEMP_STATEMENTS_FULL_DB_PATH,
        table_name="statements",
    )

    targets_count = extract_unfiltered_csv(
        csv_path=TARGETS_CSV_PATH,
        db_path=TARGETS_DB_PATH,
        temp_db_path=TEMP_TARGETS_DB_PATH,
        table_name="targets",
    )

    return statements_count, targets_count




# ==================================================
# 5. ENTRY POINT
# ==================================================

def main() -> None:
    extract_statements()
    extract_unfiltered_datasets()


if __name__ == "__main__":
    main()
