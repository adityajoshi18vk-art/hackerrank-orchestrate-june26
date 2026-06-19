import os
import sys
import json
import asyncio
import pandas as pd
from google import genai
from google.genai import types

# Add parent directory to path to import main and agents and prompts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as pipeline_main
import agents
import prompts

# Setup paths
DATASET_DIR = os.getenv("DATASET_PATH", "../dataset")
SAMPLE_CLAIMS_CSV = os.path.join(DATASET_DIR, "sample_claims.csv")
USER_HISTORY_CSV = os.path.join(DATASET_DIR, "user_history.csv")
EVAL_OUTPUT_CSV = "sample_output.csv"
REPORT_MD = "evaluation_report.md"

async def evaluate_with_gemini(expected_rows, predicted_rows):
    client = genai.Client()
    prompt = f"EXPECTED ROWS:\n{json.dumps(expected_rows, indent=2)}\n\nPREDICTED ROWS:\n{json.dumps(predicted_rows, indent=2)}"
    
    response = await client.aio.models.generate_content(
        model=agents.MODEL_NAME,
        contents=[prompts.EVALUATION_PROMPT, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    return json.loads(response.text)

async def run_evaluation():
    if not os.path.exists(SAMPLE_CLAIMS_CSV):
        print(f"Error: {SAMPLE_CLAIMS_CSV} not found.")
        return
        
    df_sample = pd.read_csv(SAMPLE_CLAIMS_CSV)
    df_history = pd.read_csv(USER_HISTORY_CSV)
    user_history_dict = df_history.set_index("user_id").to_dict(orient="index")
    
    print("Running pipeline on sample_claims.csv...")
    
    # We will run the pipeline_main.process_claim for each row in df_sample
    batch_size = 5
    all_results = []
    
    for i in range(0, len(df_sample), batch_size):
        batch = df_sample.iloc[i:i+batch_size]
        print(f"Processing evaluation batch {i//batch_size + 1}...")
        
        tasks = []
        for _, row in batch.iterrows():
            tasks.append(pipeline_main.process_claim(row.to_dict(), user_history_dict))
            
        batch_results = await asyncio.gather(*tasks)
        all_results.extend([res for res in batch_results if res is not None])
        
        if i + batch_size < len(df_sample):
            await asyncio.sleep(1)
            
    df_predicted = pd.DataFrame(all_results)
    df_predicted.to_csv(EVAL_OUTPUT_CSV, index=False)
    
    print("Pipeline complete. Running Evaluation Agent...")
    
    expected_rows = df_sample.to_dict(orient="records")
    predicted_rows = df_predicted.to_dict(orient="records")
    
    eval_results = await evaluate_with_gemini(expected_rows, predicted_rows)
    
    print("\n--- Evaluation Summary ---")
    print(f"Total Cases: {eval_results.get('total_cases')}")
    print(f"Overall Score: {eval_results.get('overall_score')}")
    
    # Write the markdown report
    with open(REPORT_MD, "w") as f:
        f.write("# Evaluation Report\n\n")
        f.write(f"**Total Cases:** {eval_results.get('total_cases')}\n")
        f.write(f"**Overall Score:** {eval_results.get('overall_score')}\n\n")
        f.write("## Accuracy Metrics\n")
        f.write(f"- Claim Status: {eval_results.get('claim_status_accuracy')}\n")
        f.write(f"- Issue Type: {eval_results.get('issue_type_accuracy')}\n")
        f.write(f"- Object Part: {eval_results.get('object_part_accuracy')}\n")
        f.write(f"- Severity: {eval_results.get('severity_accuracy')}\n")
        f.write(f"- Evidence Standard: {eval_results.get('evidence_standard_accuracy')}\n\n")
        
        f.write("## Error Analysis\n")
        f.write("### Most Common Mistakes\n")
        for mistake in eval_results.get('error_analysis', {}).get('most_common_mistakes', []):
            f.write(f"- {mistake}\n")
        f.write("\n### Problematic Cases\n")
        for case in eval_results.get('error_analysis', {}).get('problematic_cases', []):
            f.write(f"- {case}\n")
            
        f.write("\n## Per Case Results\n")
        for case in eval_results.get('per_case_results', []):
            f.write(f"### User ID: {case.get('user_id')}\n")
            f.write(f"- Match: Status={case.get('claim_status_match')}, Issue={case.get('issue_type_match')}, Part={case.get('object_part_match')}\n")
            f.write(f"- Expected: {case.get('expected_status')} | Predicted: {case.get('predicted_status')}\n")
            f.write(f"- Notes: {case.get('notes')}\n")

    print(f"\nDetailed report written to {REPORT_MD}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
