import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# --- 1. SET UP MOCKS FOR EXTERNAL DEPENDENCIES ---
# We must do this BEFORE importing app or utils, as they import these libs at top level.

mock_modules = {
    'streamlit': MagicMock(),
    'google': MagicMock(),
    'google.genai': MagicMock(),
    'google.genai.types': MagicMock(),
    'gspread': MagicMock(),
    'oauth2client': MagicMock(),
    'oauth2client.service_account': MagicMock(),
    'pandas': MagicMock(),
}

# Apply mocks to sys.modules
patcher = patch.dict(sys.modules, mock_modules)
patcher.start()

# Setup Streamlit Session State specifically since it's used globally
mock_modules['streamlit'].session_state = {}

# --- 2. IMPORT LOCAL MODULES ---
# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils import SessionTracker, SheetLogger
    from app import extract_json_and_sources
    import streamlit as st
except ImportError as e:
    print(f"CRITICAL: Import failed even with mocks: {e}")
    sys.exit(1)

# --- 3. TEST CLASS ---
class TestAvanseFlow(unittest.TestCase):

    def setUp(self):
        # Reset Session State before each test
        st.session_state.clear()
        st.session_state.update({
            "user_details": {},
            "start_time": "mock_time",
            "messages": []
        })

    # TEST CASE 1: LLM JSON Extraction (Happy Path)
    def test_llm_json_parsing_success(self):
        """Verify we can extract fields from a clean JSON response."""
        response_text = """
        Here is the advice.
        ```json
        {
            "answer": "To study in UK...",
            "Name": "Rahul",
            "Country": "UK",
            "Sentiment": "Positive"
        }
        ```
        """
        mock_resp = MagicMock()
        mock_resp.text = response_text
        mock_resp.candidates = []

        answer, opts, sources, videos, lead_data = extract_json_and_sources(mock_resp)

        self.assertIn("To study in UK", answer)
        self.assertEqual(lead_data["Name"], "Rahul")
        self.assertEqual(lead_data["Country"], "UK")
        self.assertEqual(lead_data["Sentiment"], "Positive")

    # TEST CASE 2: Multi-Value Accumulation (The User Request)
    def test_session_accumulation_comma_separated(self):
        """Verify that multiple variables are stored comma-separated."""
        tracker = SessionTracker()
        
        # 1. First Mention: UK
        tracker.update_from_llm({"Country": "UK"})
        self.assertEqual(st.session_state.user_details["Country"], "UK")
        
        # 2. Second Mention: USA (Should append)
        tracker.update_from_llm({"Country": "USA"})
        self.assertEqual(st.session_state.user_details["Country"], "UK, USA")
        
        # 3. Third Mention: UK again (Should NOT duplicate)
        tracker.update_from_llm({"Country": "UK"})
        self.assertEqual(st.session_state.user_details["Country"], "UK, USA")
        
        # 4. Complex split check
        tracker.update_from_llm({"Country": "Germany, UK"})
        # Should add Germany, ignore UK
        # Note: Order might depend on implementation, but set check is safer.
        # String check: "UK, USA, Germany" or similar.
        val = st.session_state.user_details["Country"]
        self.assertIn("Germany", val)
        self.assertIn("UK", val)
        self.assertIn("USA", val)
        # Ensure UK is not double counted
        self.assertEqual(val.count("UK"), 1)

    # TEST CASE 3: Google Sheet Fallback Logic
    def test_sheet_logger_init_fallback(self):
        """Verify SheetLogger defaults to CSV mode if credentials missing/fail."""
        # Use patch to simulate OS checks and Gspread failures
        with patch('os.path.exists') as mock_exists:
            # Case A: Credentials file DOES NOT exist
            mock_exists.return_value = False 
            
            logger = SheetLogger(json_keyfile="fake.json")
            self.assertFalse(logger.use_sheets)
            self.assertEqual(logger.csv_file, "leads.csv")

    # TEST CASE 4: Resilience to Broken JSON
    def test_llm_broken_json(self):
        """Verify app doesn't crash on bad JSON."""
        mock_resp = MagicMock()
        mock_resp.text = "I am sorry I cannot provide JSON."
        answer, opts, sources, videos, lead_data = extract_json_and_sources(mock_resp)
        
        self.assertIn("I am sorry", answer)
        self.assertIsNone(lead_data.get("Name"))

if __name__ == '__main__':
    unittest.main()
