# Operational Analysis & Evaluation Report

## 1. Workload Statistics
- **Total Claims Processed:** 64 (20 sample claims + 44 test claims)
- **Total Images Processed:** ~96 images (averaging 1.5 images per claim)
- **Model Calls:**
  - **Text (`llama-3.3-70b-versatile`):** ~128 calls (2 per claim for parsing and aggregation)
  - **Vision (`meta-llama/llama-4-scout-17b-16e-instruct`):** ~96 calls (1 per image)

## 2. Approximate Token Usage
- **Text Models:**
  - Input: ~102,400 tokens
  - Output: ~6,400 tokens
- **Vision Models:**
  - Input: ~240,000 tokens (accounting for image base64 + text prompt footprint)
  - Output: ~9,600 tokens
- **Total Tokens:** ~358,400 tokens

## 3. Cost Estimation (Groq API Assumptions)
Assuming standard competitive open-weight pricing brackets for Groq's high-speed inference:
- Llama-3.3-70b: ~$0.59 / 1M input, $0.79 / 1M output
- Llama Vision equivalents: ~$0.15 / 1M input, $0.15 / 1M output
- **Total Estimated Cost:** Less than **$0.15** to process the entire test and sample dataset.

## 4. Latency and Runtime
- **Average Claim Processing Time:** ~30-40 seconds (including network latency, multi-image vision analysis, and mandatory rate-limit buffering).
- **Total Runtime:** The 44-claim test set took approximately **20-25 minutes** to process sequentially, heavily influenced by necessary rate-limit sleeping.

## 5. TPM/RPM Considerations & Architecture Strategy

Groq's free-tier endpoints impose strict limits (e.g., 500,000 Tokens-Per-Day for Vision, 14,400 Tokens-Per-Minute for Text). To navigate this without failure:

- **Key Rotation (Pooling):** We utilized a multi-key strategy providing `GROQ_API_KEYS` in the `.env` file. The `rotate_client()` logic automatically distributes the workload.
- **Graceful Degradation (Throttling & Backoff):** The system catches `429 Rate Limit Exceeded` exceptions instantly. It dynamically switches to the next API key in the pool and implements a 2-second sleep backoff. If all keys hit RPM limits, it uses an exponential backoff retry.
- **Sequential Safety (Caching & Flushing):** Rather than batching, which risks massive data loss on API timeouts, claims are processed sequentially. Every completed claim is flushed instantly to `output.csv`. The `load_already_processed()` function checks the CSV on startup, allowing the pipeline to resume safely from where it left off without re-spending tokens on completed claims.
