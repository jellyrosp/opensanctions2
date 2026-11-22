import pandas as pd
import sqlite3
from contextlib import closing
from opensanctions2.config import STATEMENTS_FULL_DB_PATH, OUTPUT_DIR



def export_sanctioned_role_rca_persons() -> pd.DataFrame:
    """
    Export sanctioned persons with role.rca topic, gender, sanction
    reasons and additional Sanction properties.

    Population:
        Person.topics = 'role.rca'
        Person.topics IN ('sanction', 'sanction.counter')

    Multiple values for Sanction properties generate separate rows.
    When multiple properties have multiple values, their combinations
    are represented as a Cartesian product.
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
    ),

    sanction_persons AS (
        SELECT DISTINCT
            s.canonical_id AS sanction_id,
            s.value AS person_id,
            pg.value AS gender
        FROM target_persons AS p

        INNER JOIN ranked_gender AS pg
            ON p.canonical_id = pg.canonical_id
           AND pg.rn = 1

        INNER JOIN statements AS s
            ON s."schema" = 'Sanction'
           AND s.prop_type = 'entity'
           AND s.value = p.canonical_id
    )

    SELECT
        sp.person_id,
        sp.gender,
        reason.value AS sanction_reason,
        start_date.value AS startDate,
        end_date.value AS endDate,
        authority.value AS authority,
        authority_id.value AS authorityId,
        country.value AS country,
        program.value AS program,
        program_id.value AS programId,
        program_url.value AS programUrl,
        source_url.value AS sourceUrl,
        status.value AS status

    FROM sanction_persons AS sp

    INNER JOIN statements AS reason
        ON reason.canonical_id = sp.sanction_id
       AND reason."schema" = 'Sanction'
       AND reason.prop = 'reason'
       AND reason.value IS NOT NULL

    LEFT JOIN statements AS authority
        ON authority.canonical_id = sp.sanction_id
       AND authority."schema" = 'Sanction'
       AND authority.prop = 'authority'
       AND authority.value IS NOT NULL

    LEFT JOIN statements AS authority_id
        ON authority_id.canonical_id = sp.sanction_id
       AND authority_id."schema" = 'Sanction'
       AND authority_id.prop = 'authorityId'
       AND authority_id.value IS NOT NULL

    LEFT JOIN statements AS country
        ON country.canonical_id = sp.sanction_id
       AND country."schema" = 'Sanction'
       AND country.prop = 'country'
       AND country.value IS NOT NULL

    LEFT JOIN statements AS end_date
        ON end_date.canonical_id = sp.sanction_id
       AND end_date."schema" = 'Sanction'
       AND end_date.prop = 'endDate'
       AND end_date.value IS NOT NULL

    LEFT JOIN statements AS program
        ON program.canonical_id = sp.sanction_id
       AND program."schema" = 'Sanction'
       AND program.prop = 'program'
       AND program.value IS NOT NULL

    LEFT JOIN statements AS program_id
        ON program_id.canonical_id = sp.sanction_id
       AND program_id."schema" = 'Sanction'
       AND program_id.prop = 'programId'
       AND program_id.value IS NOT NULL

    LEFT JOIN statements AS program_url
        ON program_url.canonical_id = sp.sanction_id
       AND program_url."schema" = 'Sanction'
       AND program_url.prop = 'programUrl'
       AND program_url.value IS NOT NULL

    LEFT JOIN statements AS source_url
        ON source_url.canonical_id = sp.sanction_id
       AND source_url."schema" = 'Sanction'
       AND source_url.prop = 'sourceUrl'
       AND source_url.value IS NOT NULL

    LEFT JOIN statements AS start_date
        ON start_date.canonical_id = sp.sanction_id
       AND start_date."schema" = 'Sanction'
       AND start_date.prop = 'startDate'
       AND start_date.value IS NOT NULL

    LEFT JOIN statements AS status
        ON status.canonical_id = sp.sanction_id
       AND status."schema" = 'Sanction'
       AND status.prop = 'status'
       AND status.value IS NOT NULL

    ORDER BY
        sp.person_id,
        sanction_reason,
        startDate,
        endDate;
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

    return df




# ==================================================
# 5. ENTRY POINT
# ==================================================

def main() -> None:
    export_sanctioned_role_rca_persons()

if __name__ == "__main__":
    main()
