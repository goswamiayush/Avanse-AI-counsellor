import streamlit as st
import gspread
from gspread.exceptions import APIError
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import os
import json
import traceback
import uuid

# --- GOOGLE SHEETS LOGGER ---
class SheetLogger:
    def __init__(self, json_keyfile="credentials.json", sheet_id=None):
        self.headers = [
            "Session_ID", "Timestamp", "Name", "Mobile", "Email", "Country", 
            "Target_Degree", "Intended_Major", "College", "Budget", "Sentiment", 
            "Propensity", "Time_Spent", "User_Inputs_Only", "Full_Conversation_History"
        ]

        # 0. Get Sheet ID from Secrets if not provided
        if not sheet_id:
            try:
                sheet_id = st.secrets["SHEET_ID"]
            except:
                # Fallback to the hardcoded ID for safety, or error out
                sheet_id = "1xKkadZFL3HI8y544rSJeedN-irwxkVD_Qq8u2N8FwPE"
        
        self.use_sheets = False
        self.sheet = None
        
        # 1. Try connecting via File (Local)
        if os.path.exists(json_keyfile):
            try:
                scope = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                creds = ServiceAccountCredentials.from_json_keyfile_name(json_keyfile, scope)
                client = gspread.authorize(creds)
                self.sheet = client.open_by_key(sheet_id).sheet1
                print(f"✅ Successfully connected to Sheet: {self.sheet.title}")
                self.use_sheets = True
            except Exception as e:
                self.auth_error = f"File Auth Failed: {str(e)}\nTraceback: {traceback.format_exc()}"
                print(f"File Auth Error: {e}")

        # 2. Try connection via st.secrets (Cloud)
        if not self.use_sheets and "gcp_service_account" in st.secrets:
            try:
                scope = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                # Create a temporary dict from secrets to pass to the credential builder
                creds_dict = dict(st.secrets["gcp_service_account"])
                
                # Fix for potential private_key formatting issues (replace literal \n with actual newline)
                if "private_key" in creds_dict:
                    raw_key = creds_dict["private_key"]
                    creds_dict["private_key"] = raw_key.replace("\\n", "\n").replace('\\n', '\n')

                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                client = gspread.authorize(creds)
                self.sheet = client.open_by_key(sheet_id).sheet1
                print(f"✅ Successfully connected to Sheet: {self.sheet.title}")
                self.ensure_headers()
                self.use_sheets = True
            except APIError as api_err:
                if "disabled" in str(api_err):
                    self.auth_error = (
                        "📉 **Google Sheets API is Disabled** on your Google Cloud Project.\n"
                        "Please enable it here: [Enable Sheets API]"
                        "(https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=ayush-twin)"
                    )
                else:
                    self.auth_error = f"Google Sheets API Error: {str(api_err)}"
                print(f"Secrets Auth API Error: {api_err}")
            except Exception as e:
                self.auth_error = f"Secrets Auth Failed: {str(e)}"
                print(f"Secrets Auth Error: {e}")

        # 3. Fallback to CSV
        if not self.use_sheets:
             # Only show error if we expected to find sheets (i.e. not just a fresh local run without config)
             if os.path.exists(json_keyfile) or "gcp_service_account" in st.secrets:
                 err_msg = getattr(self, 'auth_error', 'Unknown Error')
                 st.error(f"⚠️ Google Sheet Connection Failed.\n\n**Error Details:** `{err_msg}`\n\nlogging locally to CSV.")
        
        self.csv_file = "leads.csv"
        if not os.path.exists(self.csv_file):
            # Create CSV with new headers
            df = pd.DataFrame(columns=self.headers)
            df.to_csv(self.csv_file, index=False)

    def ensure_headers(self):
        """Checks if the sheet is empty and adds headers if needed."""
        if not self.use_sheets or not self.sheet:
            return
        
        try:
            # Efficient check: just get the header values
            # We fetch strictly A1:O1 to avoid getting full sheet
            header_range = self.sheet.get("A1:O1")
            
            # header_range is a list of lists: [['Session_ID', ...]]
            current_headers = header_range[0] if header_range and len(header_range) > 0 else []

            if not current_headers:
                self.sheet.update("A1:O1", [self.headers])
                print("✅ Headers added to new Sheet.")
            elif current_headers != self.headers:
                print(f"⚠️ Header mismatch. Updating to ensure consistency.")
                self.sheet.update("A1:O1", [self.headers])
                
        except Exception as e:
            print(f"⚠️ Header check failed: {e}")

    def upsert_lead(self, data):
        """
        Updates existing row if Session_ID exists, else appends.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Ensure values are strings to prevent None issues
        def clean(val): return str(val) if val else ""

        row_data = [
            clean(data.get("Session_ID")),
            timestamp,
            clean(data.get("Name")),
            clean(data.get("Mobile")),
            clean(data.get("Email")),
            clean(data.get("Country")),
            clean(data.get("Target_Degree")),
            clean(data.get("Intended_Major")),
            clean(data.get("College")),
            clean(data.get("Budget")),
            clean(data.get("Sentiment", "Neutral")),
            clean(data.get("Propensity", "Low")),
            clean(data.get("Time_Spent", "0s")),
            clean(data.get("User_Inputs_Only", "")),
            clean(data.get("Full_Conversation_History", ""))
        ]

        if not self.use_sheets:
            self.append_to_csv(row_data)
            return

        try:
            # 1. Get all Session IDs (Column 1)
            # This is more efficient than get_all_records() for large sheets
            col1 = self.sheet.col_values(1)
            
            session_id = str(data.get("Session_ID"))
            
            if session_id in col1:
                # UPDATE EXISTING ROW
                # gspread is 1-indexed. Key matching row.
                row_index = col1.index(session_id) + 1
                
                # Update specific range: A{row}:O{row} (15 columns)
                cell_range = f"A{row_index}:O{row_index}"
                self.sheet.update(cell_range, [row_data])
                print(f"✅ Updated existing row {row_index} for Session: {session_id}")
                
            else:
                # APPEND NEW ROW (Manual Index calculation to fix 8-blank-cell bug)
                # append_row sometimes appends to the right if data exists in other columns
                
                next_row = len(col1) + 1
                cell_range = f"A{next_row}:O{next_row}"
                self.sheet.update(cell_range, [row_data])
                print(f"✅ Inserted new row at {next_row} for Session: {session_id}")

        except Exception as e:
            print(f"❌ Upsert Error: {e}")
            self.append_to_csv(row_data)

    def append_to_csv(self, row):
        # Check if file exists to write headers
        file_exists = os.path.exists(self.csv_file)
        
        # We need to map list row back to dict or dataframe for CSV appending with headers
        # Simpler: just append list to file
        df = pd.DataFrame([row], columns=self.headers)
        
        df.to_csv(self.csv_file, mode='a', header=not file_exists, index=False)

# --- SESSION TRACKER ---
class SessionTracker:
    def __init__(self):
        if "start_time" not in st.session_state:
            st.session_state.start_time = datetime.datetime.now()
            
        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())
            
        if "conversation_log" not in st.session_state:
            st.session_state.conversation_log = []
            
        if "user_input_log" not in st.session_state:
            st.session_state.user_input_log = []
        
        if "user_details" not in st.session_state:
            st.session_state.user_details = {
                "Name": None,
                "Mobile": None,
                "Email": None,
                "Country": None,
                "Target_Degree": None,
                "Intended_Major": None,
                "College": None,
                "Budget": None,
                "Sentiment": "Neutral",
                "Propensity": "Low"
            }

    def update_from_llm(self, extracted_data):
        """
        Updates session state with data extracted by LLM.
        Appends new unique values comma-separated for all fields.
        """
        for key, new_val in extracted_data.items():
            # Basic validation to ensure we have a real value
            if new_val and new_val not in ["null", "None", "", "N/A", "unknown"]:
                current_val = st.session_state.user_details.get(key)
                
                if current_val:
                    # Normalize and Split
                    current_list = [x.strip() for x in str(current_val).split(',')]
                    new_list = [x.strip() for x in str(new_val).split(',')]
                    
                    changed = False
                    for item in new_list:
                        # Simple deduplication (case-sensitive)
                        if item and item not in current_list:
                            current_list.append(item)
                            changed = True
                    
                    if changed:
                        st.session_state.user_details[key] = ", ".join(current_list)
                else:
                    st.session_state.user_details[key] = new_val
    
    
    def add_interaction(self, user_text, bot_text):
        """Append interaction to conversation log."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] User: {user_text} | Bot: {bot_text}"
        st.session_state.conversation_log.append(entry)
        
        # Log User Input Separately
        st.session_state.user_input_log.append(f"[{timestamp}] {user_text}")

    def get_time_spent(self):
        elapsed = datetime.datetime.now() - st.session_state.start_time
        return str(elapsed).split('.')[0] # HH:MM:SS

    def get_lead_data(self):
        data = st.session_state.user_details.copy()
        data["Session_ID"] = st.session_state.session_id
        data["Time_Spent"] = self.get_time_spent()
        
        # Join full conversation history
        data["Full_Conversation_History"] = "\n".join(st.session_state.conversation_log)
        
        # Join User Inputs Only
        data["User_Inputs_Only"] = "\n".join(st.session_state.user_input_log)
        
        return data

# --- API KEY MANAGER ---
class KeyManager:
    def __init__(self):
        # Keys storage: { "google": [], "groq": [], "cerebras": [] }
        self.keys = {
            "google": [],
            "groq": [],
            "cerebras": []
        }
        
        # Current indices
        if "key_indices" not in st.session_state:
            st.session_state.key_indices = {"google": 0, "groq": 0, "cerebras": 0}

        # 1. Load from Secrets
        self._load_from_secrets("GOOGLE_API_KEY", "google")
        self._load_from_secrets("GROQ_API_KEY", "groq")
        self._load_from_secrets("CEREBRAS_API_KEY", "cerebras")

        # 2. Load from Sidebar Input (Session State)
        self._load_from_input("input_google_keys", "google")
        self._load_from_input("input_groq_keys", "groq")
        self._load_from_input("input_cerebras_keys", "cerebras")

    def _load_from_secrets(self, secret_name, provider):
        if secret_name in st.secrets:
            # Handle comma-separated keys in secrets for power users
            secrets_val = st.secrets[secret_name]
            if "," in secrets_val:
                for k in secrets_val.split(','):
                    self._add_key(provider, k.strip())
            else:
                self._add_key(provider, secrets_val)

    def _load_from_input(self, input_key, provider):
        if input_key in st.session_state and st.session_state[input_key]:
            raw_text = st.session_state[input_key]
            for k in raw_text.split('\n'):
                self._add_key(provider, k.strip())

    def _add_key(self, provider, key):
        if key and key not in self.keys[provider]:
            self.keys[provider].append(key)

    def get_current_key(self, provider):
        if not self.keys.get(provider): return None
        idx = st.session_state.key_indices.get(provider, 0) % len(self.keys[provider])
        return self.keys[provider][idx]

    def rotate_key(self, provider):
        if not self.keys.get(provider): return None
        current = st.session_state.key_indices.get(provider, 0)
        st.session_state.key_indices[provider] = (current + 1) % len(self.keys[provider])
        print(f"🔄 Rotated {provider} key to index: {st.session_state.key_indices[provider]}")
        return self.get_current_key(provider)

# --- LLM CLIENT FACADE ---
import openai
from google import genai
from google.genai import types

class LLMClient:
    def __init__(self, key_manager):
        self.km = key_manager

    def get_response(self, provider, model_name, system_prompt, user_query, history_text):
        """
        Generic fetcher that handles provider switching and retries.
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            key = self.km.get_current_key(provider)
            if not key:
                return "⚠️ No API Key found for this provider. Please add one in Settings.", {}, [], [], {}

            try:
                if provider == "google":
                    return self._fetch_google(key, model_name, system_prompt, user_query, history_text)
                elif provider in ["groq", "cerebras"]:
                    return self._fetch_openai_compatible(provider, key, model_name, system_prompt, user_query, history_text)
                else:
                    return f"❌ Unknown provider: {provider}", {}, [], [], {}

            except Exception as e:
                error_str = str(e)
                # 429 Detection
                if "429" in error_str or "quota" in error_str.lower() or "resource_exhausted" in error_str.lower():
                    print(f"⚠️ 429 Hit on {provider}. Rotating key...")
                    self.km.rotate_key(provider)
                    continue # Retry with new key
                else:
                    return f"❌ Error: {error_str}", {}, [], [], {}
        
        return "⚠️ Quota Exhausted on all keys. Please try another provider.", {}, [], [], {}

    def _fetch_google(self, key, model, system, query, history):
        # Native Google GenAI Call
        client = genai.Client(api_key=key)
        
        # Combine history + query for context (Google style)
        full_content = f"{system}\n\nCONTEXT:\n{history}\n\nUSER: {query}"
        
        response = client.models.generate_content(
            model=model,
            contents=full_content,
            config=types.GenerateContentConfig(
                temperature=0.3,
                # system_instruction=system # Flash 1.5 prefers context in prompt usually
            )
        )
        return self._extract_json_google(response)

    def _fetch_openai_compatible(self, provider, key, model, system, query, history):
        # Base URLs
        base_urls = {
            "groq": "https://api.groq.com/openai/v1",
            "cerebras": "https://api.cerebras.ai/v1"
        }
        
        client = openai.OpenAI(
            api_key=key,
            base_url=base_urls.get(provider)
        )
        
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"CONTEXT:\n{history}\n\nUSER QUERY: {query}"}
        ]
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"} # Force JSON if supported
        )
        
        content = response.choices[0].message.content
        return self._extract_json_generic(content)

    def _extract_json_google(self, response):
        text = response.text if response.text else ""
        # Reuse existing logic or import from app.py refactor
        # For valid refactoring, we should move the extraction logic to utils or keep it in app
        # For now, let's return RAW text and let app.py parse it to minimize breakage
        # WAIT: app.py expects (answer, user_opts, sources, videos, lead_data)
        # We need to standardize this.
        
        # ... Re-implementing extraction logic here to be self-contained ...
        return self._parse_json_result(text)

    def _extract_json_generic(self, text):
        return self._parse_json_result(text)

    def _parse_json_result(self, text):
        import json
        import re
        
        # JSON Parsing
        try:
            # Try finding JSON block
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
            else:
                data = json.loads(text)
        except:
            data = {}

        # Extract Fields
        answer = data.get("answer", text) # Fallback to full text if no JSON
        user_options = data.get("user_options", [])
        videos = data.get("videos", [])
        
        # Lead Info
        lead_info = {
            "Name": data.get("Name"),
            "Mobile": data.get("Mobile"),
            "Email": data.get("Email"),
            "Country": data.get("Country"),
            "Target_Degree": data.get("Target_Degree"),
            "Intended_Major": data.get("Intended_Major"),
            "College": data.get("College"),
            "Budget": data.get("Budget"),
            "Sentiment": data.get("Sentiment"),
            "Propensity": data.get("Propensity")
        }
        
        # Sources (Mock for now or extract if provider supports it)
        sources = [] 
        
        return answer, user_options, sources, videos, lead_info

# Initialize global logger
logger = SheetLogger()
