# Multi-Modal Evidence Review System

This is the fully functioning solution for the **HackerRank Orchestrate (June 2026)** hackathon challenge. The system is designed to verify damage claims (for cars, laptops, and packages) by analyzing user conversations, historical claim patterns, and multi-modal image evidence.

## Architecture

The system utilizes an automated 5-stage AI pipeline, powered entirely by Groq's high-speed inference engine:

1. **Claim Parser**: Extracts the core claim, object, and expected issue type directly from the customer chat transcript.
2. **Risk Flagger**: Evaluates the user's past claim history (from `user_history.csv`) and flags potential abuse or repeat-review pressure.
3. **Vision Analyzer**: Uses `meta-llama/llama-4-scout-17b-16e-instruct` to perform detailed multi-modal inspection of every submitted image to check for the claimed damage.
4. **Evidence Checker**: Validates if the submitted images meet the minimum required evidence standard to make a decision.
5. **Verdict Aggregator**: Synthesizes all data points to output the final claim status (`supported`, `contradicted`, or `not_enough_information`), along with a detailed, image-grounded justification.

## Robust Rate Limit Handling & Key Rotation

Image analysis via vision models consumes a massive amount of tokens. Groq's free tier imposes a strict 500,000 Tokens-Per-Day (TPD) limit per account. To process the entire dataset without crashing or taking days:

- **Key Pooling**: The system accepts multiple Groq API keys from independent accounts.
- **Auto-Rotation**: If the pipeline encounters a `429 Rate Limit Exceeded` error, it gracefully catches the error, instantly rotates to the next available API key in the pool, and seamlessly retries the request.
- **Continuous Saving**: Claims are processed one by one and immediately appended to `output.csv`. If the pipeline is ever manually interrupted, zero data is lost.

## Getting Started

### 1. Requirements
Ensure you have Python 3.10+ installed and the required dependencies:
```bash
pip install pandas python-dotenv groq asyncio
```

### 2. Environment Setup
Create a `.env` file in the `code/` directory. To bypass the vision model's 500k TPD limits, you must provide multiple Groq keys from **separate accounts**. Separate them with commas:

```env
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
```

### 3. Running the Pipeline
Simply run the main entry point:
```bash
cd code/
python main.py
```

The script will begin processing the claims sequentially. You can open `output.csv` at any time to watch the results populate row by row in real-time.

## Project Structure

```
.
├── dataset/                    # Input data and images
│   ├── claims.csv              # The core claims to be evaluated
│   ├── user_history.csv        # Historical claim risk profiles
│   └── images/                 # Image assets referenced by claims
├── code/
│   ├── main.py                 # The main orchestrator and chunking logic
│   ├── agents.py               # API interactions, model prompts, and key rotation logic
│   ├── run_chunk.py            # Utility script for manual batch testing
│   └── retry_failed.py         # Utility script to retry specific unknown rows
├── output.csv                  # The live-updating results file
└── README.md                   # This file
```
