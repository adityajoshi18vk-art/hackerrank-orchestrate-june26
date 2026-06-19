import asyncio
import csv
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from agents import (
    run_claim_parser,
    run_image_analyzer,
    run_risk_flagger,
    run_evidence_checker,
    run_verdict_aggregator,
    DATASET_ROOT
)

CLAIMS_CSV = DATASET_ROOT / "claims.csv"
USER_HISTORY_CSV = DATASET_ROOT / "user_history.csv"
OUTPUT_CSV = Path(__file__).parent.parent / "output.csv"

OUTPUT_COLUMNS = [
    "user_id", "image_paths", "user_claim", "claim_object",
    "evidence_standard_met", "evidence_standard_met_reason",
    "risk_flags", "issue_type", "object_part", "claim_status",
    "claim_status_justification", "supporting_image_ids",
    "valid_image", "severity"
]

DELAY_BETWEEN_CLAIMS = 4      # seconds between claims
DELAY_BETWEEN_IMAGES = 3      # seconds between image calls


def load_user_history() -> dict:
    history = {}
    with open(USER_HISTORY_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            history[row["user_id"]] = row
    return history


def load_claims() -> list:
    with open(CLAIMS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_already_processed() -> set:
    """Return set of user_ids already in output.csv."""
    if not OUTPUT_CSV.exists():
        return set()
    with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {
            row["user_id"] for row in reader
            if row.get("claim_status", "unknown") != "unknown"
        }


def append_row_to_csv(row: dict, write_header: bool):
    """Append one row to output.csv immediately."""
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL
        )
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def parse_image_paths(image_paths_str: str) -> list:
    return [p.strip() for p in image_paths_str.split(";") if p.strip()]


def get_image_id(image_path: str) -> str:
    return Path(image_path).stem


def fix_booleans(row: dict) -> dict:
    for col in ["evidence_standard_met", "valid_image"]:
        val = str(row.get(col, "false")).lower().strip()
        row[col] = "true" if val == "true" else "false"
    return row


async def process_claim(row: dict, user_history: dict) -> dict:
    user_id = row["user_id"]
    image_paths_str = row["image_paths"]
    user_claim = row["user_claim"]
    claim_object = row["claim_object"]

    image_paths = parse_image_paths(image_paths_str)
    history = user_history.get(user_id, {
        "past_claim_count": "0", "accept_claim": "0",
        "manual_review_claim": "0", "rejected_claim": "0",
        "last_90_days_claim_count": "0",
        "history_flags": "none",
        "history_summary": "No history found"
    })

    # PHASE 1a — Claim parser and risk flagger (text only, fast)
    print(f"  [{user_id}] Parsing claim...")
    claim_parser_result = await run_claim_parser(user_claim, claim_object)
    await asyncio.sleep(2)

    print(f"  [{user_id}] Flagging risk...")
    risk_result = await run_risk_flagger(
        user_id, history, user_claim, claim_object
    )
    await asyncio.sleep(2)

    claimed_part = claim_parser_result.get("claimed_object_part", "unknown")

    # PHASE 1b — Images one by one with delay
    image_analyses = []
    for i, image_path in enumerate(image_paths):
        image_id = get_image_id(image_path)
        print(f"  [{user_id}] Analyzing image {i+1}/{len(image_paths)}: {image_id}...")
        analysis = await run_image_analyzer(
            image_id, image_path, claim_object, claimed_part
        )
        image_analyses.append(analysis)
        if i < len(image_paths) - 1:
            await asyncio.sleep(DELAY_BETWEEN_IMAGES)

    # PHASE 2 — Evidence checker
    print(f"  [{user_id}] Checking evidence...")
    claimed_issue = claim_parser_result.get("claimed_issue_type", "unknown")
    evidence_result = await run_evidence_checker(
        claim_object, claimed_issue, claimed_part, image_analyses
    )
    await asyncio.sleep(2)

    # PHASE 3 — Verdict
    print(f"  [{user_id}] Generating verdict...")
    original_claim = {
        "user_id": user_id,
        "image_paths": image_paths_str,
        "user_claim": user_claim,
        "claim_object": claim_object
    }
    verdict = await run_verdict_aggregator(
        original_claim, claim_parser_result,
        image_analyses, risk_result, evidence_result
    )

    # Build output row
    output_row = {col: verdict.get(col, "unknown") for col in OUTPUT_COLUMNS}
    output_row = fix_booleans(output_row)

    # Ensure no empty cells
    for col in OUTPUT_COLUMNS:
        if not output_row.get(col):
            output_row[col] = "unknown"

    return output_row


async def main():
    print("Loading data...")
    claims = load_claims()
    user_history = load_user_history()

    # Skip already successfully processed rows
    already_done = load_already_processed()
    remaining = [r for r in claims if r["user_id"] not in already_done]

    print(f"Total claims: {len(claims)}")
    print(f"Already processed: {len(already_done)}")
    print(f"Remaining: {len(remaining)}")

    # Write header only if file doesn't exist yet
    write_header = not OUTPUT_CSV.exists() or len(already_done) == 0
    if write_header and OUTPUT_CSV.exists():
        OUTPUT_CSV.unlink()  # clear old file

    if write_header:
        # Write header row
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL
            )
            writer.writeheader()

    for i, row in enumerate(remaining):
        user_id = row["user_id"]
        print(f"\n[{i+1}/{len(remaining)}] Processing {user_id}...")
        try:
            result = await process_claim(row, user_history)
            append_row_to_csv(result, write_header=False)
            print(f"  [SUCCESS] {user_id}: {result['claim_status']} | {result['issue_type']} | severity={result['severity']}")
        except Exception as e:
            print(f"  [ERROR] {user_id} failed: {e}")
            # Write placeholder so we know it failed
            fallback = {col: "unknown" for col in OUTPUT_COLUMNS}
            fallback["user_id"] = user_id
            fallback["image_paths"] = row["image_paths"]
            fallback["user_claim"] = row["user_claim"]
            fallback["claim_object"] = row["claim_object"]
            fallback["evidence_standard_met"] = "false"
            fallback["valid_image"] = "false"
            fallback["risk_flags"] = "none"
            append_row_to_csv(fallback, write_header=False)

        # Delay between claims to respect rate limits
        if i < len(remaining) - 1:
            print(f"  Waiting {DELAY_BETWEEN_CLAIMS}s before next claim...")
            await asyncio.sleep(DELAY_BETWEEN_CLAIMS)

    print(f"\nDone! output.csv updated with all {len(claims)} claims.")


if __name__ == "__main__":
    asyncio.run(main())
