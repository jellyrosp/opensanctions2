import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2_contingency, fisher_exact
from statsmodels.stats.multitest import multipletests




def gender_topic_inference(
    contingency_table: pd.DataFrame,
    min_frequency: int = 5
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """
    Perform inferential analysis of gender × topic associations.

    Topics with fewer than `min_frequency` observations in either
    gender are excluded before the inferential analysis.

    Parameters:
        contingency_table: pd.DataFrame
            Columns: topic, male_abs_freq, female_abs_freq.

        min_frequency: int
            Minimum number of observations required for each gender
            within a topic. Defaults to 5.

    Returns:
        results_df:
            Topic-level odds ratios, confidence intervals,
            p-values, adjusted p-values and log-odds.

        chi2_result:
            Global chi-square statistics.

        standardized_residuals:
            Matrix of standardized residuals.
    """

    ct = contingency_table.set_index("topic").copy()

    # Exclude topics with low frequencies in either gender.
    ct = ct[
        (ct["female_abs_freq"] >= min_frequency) &
        (ct["male_abs_freq"] >= min_frequency)
    ]

    if ct.empty:
        raise ValueError(
            "No topics remain after applying the minimum-frequency filter."
        )

    matrix = ct[["female_abs_freq", "male_abs_freq"]]

    # Global chi-square test.
    chi2, p, dof, expected = chi2_contingency(matrix)

    expected_df = pd.DataFrame(
        expected,
        index=matrix.index,
        columns=matrix.columns
    )

    standardized_residuals = (
        matrix - expected_df
    ) / np.sqrt(expected_df)

    total_female = matrix["female_abs_freq"].sum()
    total_male = matrix["male_abs_freq"].sum()

    results = []

    for topic, row in matrix.iterrows():
        female = row["female_abs_freq"]
        male = row["male_abs_freq"]

        female_other = total_female - female
        male_other = total_male - male

        table = np.array([
            [female, female_other],
            [male, male_other]
        ], dtype=float)

        # Fisher's exact test uses the original integer counts.
        oddsratio, pvalue = fisher_exact(table)

        # Apply the 0.5 correction only for effect-size estimation
        # and confidence intervals when zero cells are present.
        adjusted_table = table.copy()

        if (adjusted_table == 0).any():
            adjusted_table += 0.5

        sm_table = sm.stats.Table2x2(adjusted_table)
        ci_low, ci_high = sm_table.oddsratio_confint()

        results.append({
            "topic": topic,
            "female_abs_freq": female,
            "male_abs_freq": male,
            "odds_ratio": oddsratio,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "p_value": pvalue
        })

    results_df = pd.DataFrame(results)

    # Benjamini–Hochberg correction for multiple comparisons.
    results_df["p_adj"] = multipletests(
        results_df["p_value"],
        method="fdr_bh"
    )[1]

    results_df["log_odds"] = np.log(
        results_df["odds_ratio"].replace(0, np.nan)
    )

    results_df = results_df.sort_values(
        by="log_odds",
        key=lambda s: s.abs(),
        ascending=False
    ).reset_index(drop=True)

    chi2_result = {
        "chi2": chi2,
        "p_value": p,
        "dof": dof
    }

    return results_df, chi2_result, standardized_residuals
