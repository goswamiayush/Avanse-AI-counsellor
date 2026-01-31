import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import os
import json
import traceback

# --- GOOGLE SHEETS LOGGER ---
class SheetLogger:
    def __init__(self, json_keyfile="credentials.json", sheet_id=None):
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
                self.use_sheets = True
            except Exception as e:
                self.auth_error = f"Secrets Auth Failed: {str(e)}\nTraceback: {traceback.format_exc()}"
                print(f"Secrets Auth Error: {e}")

        # 3. Fallback to CSV
        if not self.use_sheets:
             # Only show error if we expected to find sheets (i.e. not just a fresh local run without config)
             if os.path.exists(json_keyfile) or "gcp_service_account" in st.secrets:
                 err_msg = getattr(self, 'auth_error', 'Unknown Error')
                 st.error(f"⚠️ Google Sheet Connection Failed.\n\n**Error Details:** `{err_msg}`\n\nlogging locally to CSV.")
        
        self.csv_file = "leads.csv"
        if not os.path.exists(self.csv_file):
            df = pd.DataFrame(columns=["Timestamp", "Name", "Mobile", "Email", "Country", "College", "Budget", "Sentiment", "Propensity", "Time_Spent", "Interaction_Summary"])
            df.to_csv(self.csv_file, index=False)

    def log_lead(self, data):
        """
        Logs lead data to Google Sheet or CSV.
        data: dict containing keys matching the columns
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp,
            data.get("Name", ""),
            data.get("Mobile", ""),
            data.get("Email", ""),
            data.get("Country", ""),
            data.get("College", ""),
            data.get("Budget", ""),
            data.get("Sentiment", "Neutral"),
            data.get("Propensity", "Low"),
            data.get("Time_Spent", "0s"),
            data.get("Interaction_Summary", "")
        ]

        if self.use_sheets:
            try:
                self.sheet.append_row(row)
                print("✅ Row added to Google Sheet")
            except Exception as e:
                print(f"❌ Error writing to Google Sheet: {e}")
                self.append_to_csv(row)
        else:
            self.append_to_csv(row)

    def append_to_csv(self, row):
        df = pd.DataFrame([row], columns=["Timestamp", "Name", "Mobile", "Email", "Country", "College", "Budget", "Sentiment", "Propensity", "Time_Spent", "Interaction_Summary"])
        df.to_csv(self.csv_file, mode='a', header=False, index=False)

# --- SESSION TRACKER ---
class SessionTracker:
    def __init__(self):
        if "start_time" not in st.session_state:
            st.session_state.start_time = datetime.datetime.now()
        
        if "user_details" not in st.session_state:
            st.session_state.user_details = {
                "Name": None,
                "Mobile": None,
                "Email": None,
                "Country": None,
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
    
    def get_time_spent(self):
        elapsed = datetime.datetime.now() - st.session_state.start_time
        return str(elapsed).split('.')[0] # HH:MM:SS

    def get_lead_data(self):
        data = st.session_state.user_details.copy()
        data["Time_Spent"] = self.get_time_spent()
        # Create a mini summary of the chat so far
        # (Naive approach: just last 3 interactions)
        # In a real app, we might ask LLM to summarize
        return data

# Initialize global logger
logger = SheetLogger()
