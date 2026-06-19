import asyncio
import csv
import pandas as pd
from pathlib import Path
from main import process_claim

OUTPUT_CSV = Path(__file__).parent.parent / "output.csv"
CLAIMS_CSV = Path(__file__).parent.parent / "dataset" / "claims.csv"
USER_HISTORY_CSV = Path(__file__).parent.parent / "dataset" / "user_history.csv"

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

async def main():
    # 1. Load output.csv to see what we've already done successfully
    try:
        df = pd.read_csv(OUTPUT_CSV)
        # Any row that does not have "unknown" user_id and doesn't have "unknown" claim_status is considered done
        # Wait, if claim_status is not_enough_information, is it done?
        # A valid run could result in not_enough_information. But since previous runs were broken, we treat "unknown" issue_type as failed.
        done_mask = (df["user_id"] != "unknown") & (df["claim_status"] != "unknown") & (df["issue_type"] != "unknown")
        done_ids = set(df[done_mask]["user_id"].tolist())
    except Exception:
        df = pd.DataFrame(columns=OUTPUT_COLUMNS)
        done_ids = set()

    # 2. Load all claims
    with open(CLAIMS_CSV, newline="", encoding="utf-8") as f:
        all_claims = list(csv.DictReader(f))

    # 3. Find claims that are NOT done
    pending_claims = [c for c in all_claims if c["user_id"] not in done_ids]
    
    if not pending_claims:
        print("All 44 claims have been successfully processed!")
        return

    # 4. Take the next 1 claim
    chunk = pending_claims[:1]
    print(f"Found {len(pending_claims)} pending claims. Processing next {len(chunk)}...")

    user_history = load_user_history()
    
    # Process
    for i, row in enumerate(chunk):
        print(f"[{i+1}/{len(chunk)}] Processing {row['user_id']}...")
        result = await process_claim(row, user_history)
        
        # Save to df immediately
        if row["user_id"] in df["user_id"].values:
            idx = df[df["user_id"] == row["user_id"]].index[0]
            for col in OUTPUT_COLUMNS:
                df.at[idx, col] = result.get(col, "unknown")
        else:
            new_row = pd.DataFrame([result])
            df = pd.concat([df, new_row], ignore_index=True)
            
        df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL)
        
        # Wait slightly between items
        await asyncio.sleep(2)
        
    print(f"\nFinished batch! Run this script again to process the next {len(chunk)}.")

if __name__ == "__main__":
    asyncio.run(main())
