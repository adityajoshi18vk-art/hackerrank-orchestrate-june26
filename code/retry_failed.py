import asyncio
import csv
import json
import pandas as pd
from pathlib import Path
from agents import (
    run_claim_parser, run_image_analyzer, run_risk_flagger,
    run_evidence_checker, run_verdict_aggregator, DATASET_ROOT
)

OUTPUT_CSV = Path(__file__).parent.parent / "output.csv"
CLAIMS_CSV = DATASET_ROOT / "claims.csv"
USER_HISTORY_CSV = DATASET_ROOT / "user_history.csv"

OUTPUT_COLUMNS = [
    "user_id", "image_paths", "user_claim", "claim_object",
    "evidence_standard_met", "evidence_standard_met_reason",
    "risk_flags", "issue_type", "object_part", "claim_status",
    "claim_status_justification", "supporting_image_ids",
    "valid_image", "severity"
]

def load_user_history():
    history = {}
    with open(USER_HISTORY_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            history[row["user_id"]] = row
    return history

async def process_single(row, user_history):
    """Process one claim row through full pipeline."""
    from main import process_claim
    return await process_claim(row, user_history)

async def main():
    # Load current output
    df = pd.read_csv(OUTPUT_CSV)
    
    # Find failed rows
    failed_mask = (
        (df["claim_status"] == "unknown") |
        (df["user_id"] == "unknown") |
        (df["issue_type"] == "unknown") & (df["claim_status"] == "not_enough_information")
    )
    failed_ids = df[failed_mask]["user_id"].tolist()[:5]
    print(f"Found {len(failed_ids)} failed rows: {failed_ids}")
    
    if not failed_ids:
        print("No failures! Output is clean.")
        return

    # Load original claims for failed rows
    with open(CLAIMS_CSV, newline="", encoding="utf-8") as f:
        all_claims = list(csv.DictReader(f))
    
    failed_claims = [r for r in all_claims if r["user_id"] in failed_ids]
    user_history = load_user_history()

    # Reprocess one at a time (safest)
    fixed = {}
    for i, row in enumerate(failed_claims):
        print(f"Retrying {i+1}/{len(failed_claims)}: {row['user_id']}...")
        try:
            result = await process_single(row, user_history)
            fixed[row["user_id"]] = result
            print(f"  ✅ {row['user_id']}: {result.get('claim_status')}")
        except Exception as e:
            print(f"  ❌ {row['user_id']}: {e}")
        await asyncio.sleep(2)

    # Merge fixes into dataframe
    for uid, result in fixed.items():
        for col in OUTPUT_COLUMNS:
            df.loc[df["user_id"] == uid, col] = result.get(col, "unknown")

    # Save updated output
    df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL)
    print(f"\nDone! Fixed {len(fixed)} rows. Output saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())
