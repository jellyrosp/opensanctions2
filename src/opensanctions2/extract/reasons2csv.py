import pandas as pd
import sqlite3
from contextlib import closing
from opensanctions2.config import STATEMENTS_FULL_DB_PATH, OUTPUT_DIR


def export_sanctioned_role_rca_persons() -> pd.DataFrame:
    """
    Export sanctioned persons with role.rca topic, gender and sanction reasons.

    Population:
        Person.topics = 'role.rca'
        Person.topics IN ('sanction', 'sanction.counter')

    Columns:
        person_id, gender, sanction_reason
    """

    query = """
    WITH target_persons AS (
        SELECT canonical_id
        FROM statements
        WHERE "schema" = 'Person'
          AND prop = 'topics'
          AND value = 'role.rca'

        INTERSECT

        SELECT canonical_id
        FROM statements
        WHERE "schema" = 'Person'
          AND prop = 'topics'
          AND value IN ('sanction', 'sanction.counter')
    ),

    ranked_gender AS (
        SELECT
            canonical_id,
            value,
            ROW_NUMBER() OVER (
                PARTITION BY canonical_id
                ORDER BY rowid
            ) AS rn
        FROM statements
        WHERE "schema" = 'Person'
          AND prop = 'gender'
          AND value IN ('male', 'female')
    )

    SELECT DISTINCT
        p.canonical_id AS person_id,
        pg.value AS gender,
        s2.value AS sanction_reason

    FROM target_persons AS p

    INNER JOIN ranked_gender AS pg
        ON p.canonical_id = pg.canonical_id
       AND pg.rn = 1

    INNER JOIN statements AS s
        ON s."schema" = 'Sanction'
       AND s.prop_type = 'entity'
       AND s.value = p.canonical_id

    INNER JOIN statements AS s2
        ON s.canonical_id = s2.canonical_id
       AND s2."schema" = 'Sanction'
       AND s2.prop = 'reason'
       AND s2.value IS NOT NULL

    ORDER BY
        person_id,
        sanction_reason;
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_csv = OUTPUT_DIR / "sanctioned_role_rca_persons.csv"

    with closing(sqlite3.connect(STATEMENTS_FULL_DB_PATH)) as connection:
        df = pd.read_sql_query(query, connection)

    df.to_csv(output_csv, index=False)

    unique_persons = df["person_id"].nunique()

    print(f"Exported {len(df):,} rows to {output_csv}")
    print(f"Unique persons: {unique_persons:,}")
    print(f"Columns: {', '.join(df.columns)}")

      


# ==================================================
# 5. ENTRY POINT
# ==================================================

def main() -> None:
    export_sanctioned_role_rca_persons()

if __name__ == "__main__":
    main()
