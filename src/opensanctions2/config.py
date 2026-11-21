from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

# filtered statements dataset 
STATEMENTS_CSV_PATH = INPUT_DIR / "statements.csv"
STATEMENTS_FILTERED_DB_PATH = OUTPUT_DIR / "statements_filtered.sqlite"
TEMP_STATEMENTS_FILTERED_DB_PATH = OUTPUT_DIR / "statements_filtered.tmp.sqlite"

# full statements dataset
STATEMENTS_FULL_DB_PATH = OUTPUT_DIR / "statements_full.sqlite"
TEMP_STATEMENTS_FULL_DB_PATH = OUTPUT_DIR / "statements_full.tmp.sqlite"

# consolidated sanctions dataset (target.simple)
TARGETS_CSV_PATH = INPUT_DIR / "targets.simple.csv"
TARGETS_DB_PATH = OUTPUT_DIR / "targets_simple.sqlite"
TEMP_TARGETS_DB_PATH = OUTPUT_DIR / "targets_simple.tmp.sqlite"

