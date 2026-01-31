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
            # Efficient check: just get the first row
            first_row = self.sheet.row_values(1)
            
            if not first_row:
                self.sheet.append_row(self.headers)
                print("✅ Headers added to new Sheet.")
            elif first_row != self.headers:
                # OPTIONAL: If headers mismatch, we could update them.
                # Ideally, we should check if it's safe to update.
                # For now, let's just log it to avoid overwriting data.
                print(f"⚠️ Header mismatch. Expected: {self.headers} | Found: {first_row}")
                # FORCE UPDATE HEADERS (Use with caution - user asked to "fix" it)
                # self.sheet.update("A1:O1", [self.headers])
                pass 
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
                # APPEND NEW ROW
                self.sheet.append_row(row_data)
                print(f"✅ Appended new row for Session: {session_id}")

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

# Initialize global logger
logger = SheetLogger()
