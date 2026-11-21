
import sqlite3
from contextlib import closing
import pandas as pd

from opensanctions2.config import STATEMENTS_FILTERED_DB_PATH, STATEMENTS_FULL_DB_PATH, OUTPUT_DIR
from opensanctions2.constants import VALID_DATASETS, TOPIC_LABELS
from opensanctions2.stats.descriptive.aux import aggregate_datasets


def count_sanctioned_individual() -> int:
    """
    Count the distinct canonical identifiers in the extracted
    sanctioned-individual statements database.

    Returns:
        int: Number of distinct canonical IDs.
    """

    if not STATEMENTS_FILTERED_DB_PATH.is_file():
        raise FileNotFoundError(
            f"SQLite database not found: {STATEMENTS_FILTERED_DB_PATH}"
        )

    query = """
        SELECT COUNT(DISTINCT canonical_id)
        FROM statements;
    """

    with closing(sqlite3.connect(STATEMENTS_FILTERED_DB_PATH)) as connection:
        result = connection.execute(query).fetchone()

    return result[0]



def gender_statement_distribution() -> pd.DataFrame:
    """
    Calculate the distribution of sanctioned individuals
    with and without gender statements.

    Returns:
        pd.DataFrame: Absolute and relative frequencies.
    """

    if not STATEMENTS_FILTERED_DB_PATH.is_file():
        raise FileNotFoundError(
            f"SQLite database not found: {STATEMENTS_FILTERED_DB_PATH}"
        )

    query = """
        WITH individuals AS (
            SELECT DISTINCT canonical_id
            FROM statements
        ),
        gender_status AS (
            SELECT
                individuals.canonical_id,
                CASE
                    WHEN COUNT(gender.canonical_id) > 0
                        THEN 'with_gender'
                    ELSE 'without_gender'
                END AS status
            FROM individuals
            LEFT JOIN statements AS gender
                ON individuals.canonical_id = gender.canonical_id
                AND gender.prop = 'gender'
            GROUP BY individuals.canonical_id
        )
        SELECT
            status AS gender_status,
            COUNT(*) AS abs_freq
        FROM gender_status
        GROUP BY status;
    """

    with closing(sqlite3.connect(STATEMENTS_FILTERED_DB_PATH)) as connection:
        df = pd.read_sql_query(query, connection)

    total = count_sanctioned_individual()

    df["rel_freq"] = (
        df["abs_freq"] / total
    ).round(4)

    return df




def gender_values_distribution() -> pd.DataFrame:
    """
    Calculate the distribution of gender values among individuals
    with gender statements.

    Gender values are normalized by removing surrounding whitespace
    and converting to lowercase. Values other than 'male' and 'female'
    are classified as 'other'.

    Only one gender value per individual is considered: the first
    statement according to SQLite rowid.

    Returns:
        pd.DataFrame: Gender values, absolute frequencies, and
        relative frequencies.
    """

    if not STATEMENTS_FILTERED_DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {STATEMENTS_FILTERED_DB_PATH}"
        )

    # Reuse the existing gender statement distribution
    gender_stats = gender_statement_distribution()

    total_with_gender = int(
        gender_stats.loc[
            gender_stats["gender_status"] == "with_gender",
            "abs_freq"
        ].iloc[0]
    )

    query = """
        WITH ranked_gender AS (
            SELECT
                canonical_id,
                CASE
                    WHEN LOWER(TRIM(value)) = 'male' THEN 'male'
                    WHEN LOWER(TRIM(value)) = 'female' THEN 'female'
                    ELSE 'other'
                END AS gender_value,
                ROW_NUMBER() OVER (
                    PARTITION BY canonical_id
                    ORDER BY rowid
                ) AS rn
            FROM statements
            WHERE prop = 'gender'
              AND value IS NOT NULL
        )

        SELECT
            gender_value,
            COUNT(*) AS abs_freq
        FROM ranked_gender
        WHERE rn = 1
        GROUP BY gender_value
    """

    with closing(sqlite3.connect(STATEMENTS_FILTERED_DB_PATH)) as conn:
        df = pd.read_sql_query(query, conn)

    # Ensure all three categories are represented
    df = (
        df.set_index("gender_value")
        .reindex(["female", "male", "other"], fill_value=0)
        .reset_index()
    )

    df["rel_freq"] = (
        df["abs_freq"] / total_with_gender
    ).round(4)

    return df




def gender_datasets_distribution() -> pd.DataFrame:
    """
    Calculate the distribution of individuals whose gender information
    is provided by valid or non-valid datasets.

    An individual is classified as 'valid_dataset' if at
    least one of their gender statements originates from a dataset
    included in VALID_DATASET_VALUES.

    Individuals with gender statements exclusively from other datasets
    are classified as 'not_valid_dataset'.

    Returns:
        pd.DataFrame: Status, absolute frequency, and relative frequency.
    """

    if not STATEMENTS_FILTERED_DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {STATEMENTS_FILTERED_DB_PATH}"
        )

    # Reuse the existing gender statement distribution
    gender_stats = gender_statement_distribution()

    total_with_gender = int(
        gender_stats.loc[
            gender_stats["gender_status"] == "with_gender",
            "abs_freq"
        ].iloc[0]
    )

    valid_datasets = tuple(VALID_DATASETS)

    if not valid_datasets:
        raise ValueError("VALID_DATASET_VALUES cannot be empty.")

    placeholders = ", ".join("?" for _ in valid_datasets)
    query = f"""
        WITH gendered_individuals AS (
            SELECT
                canonical_id,
                MAX(
                    CASE
                        WHEN dataset IN ({placeholders}) THEN 1
                        ELSE 0
                    END
                ) AS has_valid_dataset
            FROM statements
              WHERE prop = 'gender'
              AND value IS NOT NULL
            GROUP BY canonical_id
        )
        SELECT
            CASE
                WHEN has_valid_dataset = 1
                    THEN 'valid_dataset'
                ELSE 'not_valid_dataset'
            END AS status,
            COUNT(*) AS abs_freq
        FROM gendered_individuals
        GROUP BY has_valid_dataset
    """
    with closing(sqlite3.connect(STATEMENTS_FILTERED_DB_PATH)) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=valid_datasets
        )
    df = (
        df.set_index("status")
        .reindex(
            [
                "valid_dataset",
                "not_valid_dataset"
            ],
            fill_value=0
        )
        .reset_index()
    )
    df["rel_freq"] = (
        df["abs_freq"] / total_with_gender
    ).round(4)

    return df




def gender_valid_datasets_distribution() -> pd.DataFrame:
    """
    Calculate gender information coverage across aggregated
    valid dataset groups.

    Individuals are counted once per dataset and classified
    according to whether that dataset provides a non-NULL
    gender value.

    Individuals can occur in multiple datasets.
    """

    if not STATEMENTS_FILTERED_DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {STATEMENTS_FILTERED_DB_PATH}"
        )

    valid_datasets = tuple(VALID_DATASETS)

    if not valid_datasets:
        raise ValueError("VALID_DATASETS cannot be empty.")

    placeholders = ", ".join("?" for _ in valid_datasets)

    query = f"""
        WITH dataset_individuals AS (
            SELECT DISTINCT
                canonical_id,
                dataset
            FROM statements
            WHERE dataset IN ({placeholders})
              AND canonical_id IS NOT NULL
        ),

        gendered_individuals AS (
            SELECT DISTINCT
                canonical_id,
                dataset
            FROM statements
            WHERE prop = 'gender'
              AND value IS NOT NULL
              AND dataset IN ({placeholders})
        ),

        gender_availability AS (
            SELECT
                di.canonical_id,
                di.dataset,
                CASE
                    WHEN gi.canonical_id IS NOT NULL
                        THEN 'gender'
                    ELSE 'not_gender'
                END AS gender_status
            FROM dataset_individuals AS di
            LEFT JOIN gendered_individuals AS gi
                ON di.canonical_id = gi.canonical_id
               AND di.dataset = gi.dataset
        )

        SELECT
            dataset,
            gender_status,
            COUNT(DISTINCT canonical_id) AS abs_freq
        FROM gender_availability
        GROUP BY dataset, gender_status
    """

    with closing(sqlite3.connect(STATEMENTS_FILTERED_DB_PATH)) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=valid_datasets * 2
        )

    # Aggregate dataset identifiers
    dataset_mapping = aggregate_datasets(valid_datasets)

    df["dataset_group"] = df["dataset"].map(dataset_mapping)

    # Aggregate absolute frequencies
    df = (
        df.groupby(
            ["dataset_group", "gender_status"],
            as_index=False
        )["abs_freq"]
        .sum()
    )

    # Reshape gender availability into separate columns
    df = df.pivot(
        index="dataset_group",
        columns="gender_status",
        values="abs_freq"
    ).fillna(0)

    # Ensure both categories are represented
    df = df.reindex(
        columns=["gender", "not_gender"],
        fill_value=0
    ).astype(int)

    # Calculate relative frequencies within each dataset group
    total = df["gender"] + df["not_gender"]

    df["gender_rel"] = df["gender"] / total
    df["not_gender_rel"] = df["not_gender"] / total

    # Rename columns
    df = df.rename(columns={
        "gender": "gender_abs",
        "not_gender": "not_gender_abs"
    })

    # Round relative frequencies
    df[["gender_rel", "not_gender_rel"]] = (
        df[["gender_rel", "not_gender_rel"]].round(4)
    )

    return (
        df.reset_index()
        .rename(columns={"dataset_group": "dataset"})
        [[
            "dataset",
            "gender_abs",
            "gender_rel",
            "not_gender_abs",
            "not_gender_rel"
        ]]
        .sort_values("dataset")
        .reset_index(drop=True)
    )






def gender_topics_distribution() -> pd.DataFrame:
    """
    Calculate the distribution of gender across topics.

    Each individual is assigned their first available gender statement.
    Individuals can be associated with multiple topics.

    Returns:
        pd.DataFrame: Topic, topic label, absolute and relative
        frequencies for male and female individuals.
    """

    if not STATEMENTS_FILTERED_DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {STATEMENTS_FILTERED_DB_PATH}"
        )

    topics = tuple(TOPIC_LABELS)

    if not topics:
        raise ValueError("TOPIC_LABELS cannot be empty.")

    placeholders = ", ".join("?" for _ in topics)

    query = f"""
        WITH ranked_gender AS (
            SELECT
                canonical_id,
                CASE
                    WHEN LOWER(TRIM(value)) = 'male' THEN 'male'
                    WHEN LOWER(TRIM(value)) = 'female' THEN 'female'
                    ELSE 'other'
                END AS gender,
                ROW_NUMBER() OVER (
                    PARTITION BY canonical_id
                    ORDER BY rowid
                ) AS rn
            FROM statements
            WHERE prop = 'gender'
              AND value IS NOT NULL
        ),

        first_gender AS (
            SELECT canonical_id, gender
            FROM ranked_gender
            WHERE rn = 1
              AND gender IN ('male', 'female')
        ),

        individual_topics AS (
            SELECT DISTINCT
                canonical_id,
                value AS topic
            FROM statements
            WHERE prop = 'topics'
              AND value IN ({placeholders})
        )

        SELECT
            it.topic,
            fg.gender,
            COUNT(DISTINCT fg.canonical_id) AS abs_freq
        FROM individual_topics AS it
        INNER JOIN first_gender AS fg
            ON it.canonical_id = fg.canonical_id
        GROUP BY it.topic, fg.gender
        ORDER BY it.topic, fg.gender
    """

    with closing(sqlite3.connect(STATEMENTS_FILTERED_DB_PATH)) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=topics
        )

        # Add human-readable topic labels
    df["topic"] = df["topic"].map(TOPIC_LABELS)

    # Reshape gender categories into separate columns
    df = df.pivot(
        index="topic",
        columns="gender",
        values="abs_freq"
    ).fillna(0)

    # Ensure both gender categories are represented
    df = df.reindex(
        columns=["male", "female"],
        fill_value=0
    ).astype(int)

    # Calculate relative frequencies within each topic
    total = df["male"] + df["female"]

    df["male_rel_freq"] = df["male"] / total
    df["female_rel_freq"] = df["female"] / total

    # Rename absolute-frequency columns
    df = df.rename(columns={
        "male": "male_abs_freq",
        "female": "female_abs_freq"
    })

    df = df.rename_axis("topic").reset_index()

    # Round relative frequencies
    df[["male_rel_freq", "female_rel_freq"]] = (
        df[["male_rel_freq", "female_rel_freq"]].round(4)
    )

    return df[
        [
            "topic",
            "male_abs_freq",
            "female_abs_freq",
            "male_rel_freq",
            "female_rel_freq"
        ]
    ].sort_values("topic").reset_index(drop=True)