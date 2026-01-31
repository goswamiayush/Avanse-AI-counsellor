# AI Counselor Test Suite

This directory contains robust unit tests to verify the core logic of the AI Counselor, specifically:
1.  **Lead Data Extraction**: Tests if the system correctly parses JSON from the AI, even with noise.
2.  **Session Tracking**: Verifies that user details (e.g., Country, Budget) are accumulated correctly across the conversation (e.g., "UK" + "USA" -> "UK, USA").
3.  **Resilience**: Checks that the system falls back to `leads.csv` if Google Sheets fails.

## How to Run Tests

Prerequisites:
- Python 3.8+
- Installed requirements (`pip install -r requirements.txt`) OR use the provided mocked simulation which requires no external API keys.

### Running the Validation Suite
The included `test_simulation.py` mocks all external dependencies (Google API, Streamlit, Sheets), allowing you to test the *logic* instantly without setting up keys.

```bash
python tests/test_simulation.py
```

## What is Tested?
- **Happy Path**: JSON is parsed, variables are stored.
- **Edge Cases**: Broken JSON, Missing fields, Null values.
- **Multi-Value Logic**: Verifies comma-separated accumulation.
- **Infrastructure**: Verifies fallback logging mechanisms.
