from typing import Iterable
from opensanctions2.constants import VALID_DATASETS


def render_table(dataframe: pd.DataFrame) -> None:
    """Render a formatted DataFrame in a Jupyter notebook."""

    display(
        dataframe.style
        .hide(axis="index")
        .format({
            "gender_rel": "{:.2%}",
            "gender_abs": "{:.0f}",
            "not_gender_abs": "{:.0f}",
            "not_gender_rel": "{:.2%}",
            "abs_freq": "{:.0f}",
            "male_abs_freq": "{:.0f}",
            "female_abs_freq": "{:.0f}",
            "rel_freq": "{:.2%}",
            "male_rel_freq": "{:.2%}",
            "female_rel_freq": "{:.2%}"
        })
    )




def aggregate_datasets(valid_datasets: Iterable[str]) -> dict[str, str]:
    """Aggregate dataset identifiers by their country/prefix."""

    aggregated = {}

    for dataset in valid_datasets:
        underscore_pos = dataset.find("_")
        hyphen_pos = dataset.find("-")

        separators = [
            pos for pos in (underscore_pos, hyphen_pos)
            if pos >= 0
        ]

        if separators:
            prefix = dataset[:min(separators)]
        else:
            prefix = dataset

        aggregated[dataset] = prefix.lower()

    return aggregated






