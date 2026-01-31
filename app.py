import streamlit as st
from google import genai
from google.genai import types
import json
import re
import random
import time
from utils import SessionTracker, logger

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Avanse AI Counselor",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize Session Tracker
tracker = SessionTracker()

# --- 2. IOS-STYLE MODERN CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=San+Francisco:wght@400;500;600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* GLOBAL THEME */
    .stApp {
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* HIDE DEFAULT STREAMLIT ELEMENTS */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* IOS HEADER */
    .sticky-header {
        position: fixed; top: 0; left: 0; width: 100%;
        background: rgba(249, 249, 249, 0.85); /* iOS System Gray 6 with opacity */
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);
        padding: 0.8rem 0;
        z-index: 999;
        text-align: center;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .header-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        line-height: 1.2;
    }
    .header-title {
        color: #000;
        font-size: 1rem;
        font-weight: 600;
    }
    .header-subtitle {
        color: #8E8E93; /* iOS Gray Label */
        font-size: 0.75rem;
        font-weight: 400;
    }
    .header-logo-img {
        height: 24px;
        margin-right: 8px;
    }

    .block-container { padding-top: 6rem !important; padding-bottom: 10rem !important; }

    /* CHAT MESSAGE BUBBLES - IOS STYLE */
    .stChatMessage { background-color: transparent !important; border: none !important; padding: 0.5rem 0rem !important; }
    
    /* ASSISTANT BUBBLE (Gray, Left) */
    div[data-testid="chatAvatarIcon-assistant"] { display: none; } /* Hide Avatar */
    div[data-testid="chatAvatarIcon-assistant"] + div {
        background-color: #E9E9EB; /* iOS Gray Message */
        color: #000000;
        border-radius: 18px 18px 18px 4px;
        padding: 10px 16px;
        max-width: 80%;
        float: left;
        margin-right: auto;
        box-shadow: none;
        font-size: 0.95rem;
        line-height: 1.4;
        position: relative;
    }
    /* Tail for Assistant */
    div[data-testid="chatAvatarIcon-assistant"] + div::before {
        content: "";
        position: absolute;
        bottom: 0px;
        left: -8px;
        width: 20px;
        height: 20px;
        background-color: #E9E9EB;
        border-bottom-right-radius: 16px;
        z-index: -1;
    }
    div[data-testid="chatAvatarIcon-assistant"] + div::after {
        content: "";
        position: absolute;
        bottom: 0px;
        left: -10px;
        width: 10px;
        height: 20px;
        background-color: #ffffff; /* Match BG */
        border-bottom-right-radius: 10px;
        z-index: -1;
    }

    /* USER BUBBLE (Blue, Right) */
    div[data-testid="chatAvatarIcon-user"] { display: none; } /* Hide Avatar */
    div[data-testid="chatAvatarIcon-user"] + div {
        background: linear-gradient(135deg, #007AFF 0%, #0056b3 100%); /* iOS Blue */
        color: #FFFFFF !important;
        border-radius: 18px 18px 4px 18px;
        padding: 10px 16px;
        max-width: 80%;
        float: right;
        margin-left: auto;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        font-size: 0.95rem;
    }
    div[data-testid="chatAvatarIcon-user"] + div p { color: #FFFFFF !important; }

    /* SOURCE CHIPS */
    .source-container { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
    .source-chip {
        display: inline-flex; align-items: center;
        background-color: #ffffff;
        border: 1px solid #d1d1d6;
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 0.7rem;
        color: #007AFF;
        text-decoration: none;
        transition: all 0.2s;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .source-chip:hover {
        background-color: #f2f2f7;
    }

    /* SUGGESTION BUTTONS */
    .suggestion-label { 
        font-size: 0.75rem; 
        color: #8E8E93; 
        font-weight: 500; 
        text-transform: uppercase; 
        letter-spacing: 0.5px;
        margin: 20px 0 10px 0; 
        text-align: center;
    }
    .stButton button {
        width: 100%;
        border-radius: 20px;
        border: 1px solid #E5E7EB;
        background-color: #fff;
        color: #007AFF;
        padding: 0.6rem;
        text-align: center;
        font-size: 0.9rem;
        font-weight: 400;
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        background-color: #f2f2f7;
    }

    /* LOADING ANIMATION */
    .loader-container {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        padding: 10px;
        background: #E9E9EB;
        border-radius: 18px;
        width: fit-content;
        margin-bottom: 10px;
        animation: pulse 1.5s infinite ease-in-out;
    }
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    .loader-dots {
        display: flex;
        gap: 4px;
    }
    .dot {
        width: 8px;
        height: 8px;
        background-color: #8E8E93;
        border-radius: 50%;
    }
    .loader-text {
        margin-left: 10px; 
        font-size: 0.85rem; 
        color: #636366;
        font-style: italic;
    }

</style>
""", unsafe_allow_html=True)

# --- 3. HEADER ---
st.markdown("""
<div class="sticky-header">
    <div class="header-content">
        <div class="header-title">Avanse AI Counselor</div>
        <div class="header-subtitle">Your Study Abroad Expert</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 4. API SETUP ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("⚠️ API Key missing.")
    st.stop()

client = genai.Client(api_key=api_key)

# --- 5. STATE MANAGEMENT ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! 👋 I'm your Avanse Education Expert.\n\nI can help you with Universities, Visas, and Loans. To get started, may I know your **Name** and **Target Country**?"}
    ]

if "suggestions" not in st.session_state:
    st.session_state.suggestions = ["USA", "UK", "Germany", "Canada"]

# --- FACTS FOR ENGAGEMENT HOOK ---
FACTS = [
    "Did you know? 🌍 Over 1 million international students choose the USA for their studies every year!",
    "Fun Fact: 🎓 STEM degree holders in the USA can get up to 3 years of work authorization (OPT).",
    "Insight: 💡 Germany offers tuition-free education at many public universities for international students.",
    "Did you know? 🇬🇧 The UK offers a 2-Year Graduate Route Visa for post-study work opportunities.",
    "Fact: 🇨🇦 Canada's PGWP allows you to work for up to 3 years after graduation!",
    "Tip: 📝 Building a strong profile with projects and research papers boosts your admission chances significantly.",
    "Did you know? 💰 Scholarships in the US are merit-based and can cover up to 100% of tuition!",
    "Insight: 🌏 Australia offers excellent post-study work rights, especially in regional areas.",
    "Fact: 🏥 The US healthcare sector is projected to grow much faster than the average for all occupations.",
    "Did you know? 💻 Computer Science graduates consistently have some of the highest starting salaries globally."
]

# --- 6. LOGIC FUNCTIONS ---
def extract_json_and_sources(response):
    text = response.text if response.text else ""
    sources = []
    
    # Grounding
    if response.candidates and response.candidates[0].grounding_metadata:
        md = response.candidates[0].grounding_metadata
        if md.grounding_chunks:
            for chunk in md.grounding_chunks:
                if chunk.web:
                    sources.append({"title": chunk.web.title, "url": chunk.web.uri})

    # JSON Parsing
    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
    data = {}
    if json_match:
        try:
            data = json.loads(json_match.group(1))
        except:
            pass 

    answer = data.get("answer")
    user_options = data.get("user_options", [])
    videos = data.get("videos", [])
    
    # Extra Metadata for Session Tracking
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

    if not answer:
        # Fallback
        answer = re.sub(r'user_options:.*', '', text, flags=re.DOTALL).strip()
        answer = re.sub(r'videos:.*', '', answer, flags=re.DOTALL).strip()
        answer = re.sub(r'```json', '', answer).replace('```', '').strip()

    return answer, user_options, sources, videos, lead_info

def format_history(messages):
    return "\n".join([f"{m['role']}: {m['content']}" for m in messages[-10:]]) # Increased context window

def get_gemini_response(query, history):
    try:
        # UPDATED SYSTEM PROMPT FOR DATA CAPTURE
        system_prompt = f"""
        You are an expert AI Education Counselor for Avanse Financial Services.
        Current Date: {time.strftime("%B %Y")}
        
        GOAL:
        1. Guide the student on Study Abroad (Uni, Visa, Loans).
        2. NATURALLY gather: Name, Mobile, Email, Country, Target Degree (Masters/Bachelors), Intended Major (CS/MBA/etc), College, Budget. Do NOT force it. Ask one by one if missing.
        3. Assess 'Sentiment' (Positive/Neutral/Negative) and 'Propensity' (High/Medium/Low) for conversion.
        4. CRITICAL: If the user mentions multiple items (e.g., "USA and UK", "CS and Data Science"), return them as logical COMMA-SEPARATED strings in the JSON (e.g., "USA, UK").
        
        OUTPUT FORMAT: Strict JSON ONLY.
        {{
            "answer": "Markdown response. Use emojis. Professional but friendly.",
            "user_options": ["Short Reply 1", "Short Reply 2"],
            "videos": ["youtube_link_1"],
            "Name": "Extracted or null",
            "Mobile": "Extracted or null",
            "Email": "Extracted or null",
            "Country": "Extracted or null",
            "Target_Degree": "Extracted or null",
            "Intended_Major": "Extracted or null",
            "College": "Extracted or null",
            "Budget": "Extracted or null",
            "Sentiment": "Positive/Neutral/Negative",
            "Propensity": "High/Medium/Low"
        }}
        
        CONTEXT:
        {history}
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=query,
            config=types.GenerateContentConfig(
                temperature=0.3, 
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction=system_prompt
            )
        )
        return extract_json_and_sources(response)

    except Exception as e:
        return f"⚠️ Connection Issue: {str(e)}", [], [], [], {}

# --- 7. UI COMPONENT RENDERING ---
def render_message(role, content, sources=None, videos=None):
    with st.chat_message(role):
        st.markdown(content)
        
        if sources:
            links_html = '<div class="source-container">'
            for s in sources:
                title = s["title"][:20] + ".." if len(s["title"]) > 20 else s["title"]
                links_html += f'<a href="{s["url"]}" target="_blank" class="source-chip">🔗 {title}</a>'
            links_html += '</div>'
            st.markdown(links_html, unsafe_allow_html=True)
            
        if videos:
            with st.expander("📺 Watch Videos", expanded=False):
                cols = st.columns(min(len(videos), 2))
                for i, vid_url in enumerate(videos):
                    with cols[i % 2]:
                        if "youtube.com" in vid_url or "youtu.be" in vid_url:
                            st.video(vid_url)
                        else:
                            st.markdown(f"[Watch Video]({vid_url})")

# --- 8. MAIN APP LOOP ---

# A. Render Chat History
for msg in st.session_state.messages:
    render_message(msg["role"], msg["content"], msg.get("sources"), msg.get("videos"))

# B. Render Suggestions
st.markdown('<div class="suggestion-label">Suggested Replies</div>', unsafe_allow_html=True)
selected_suggestion = None

if st.session_state.suggestions:
    cols = st.columns(len(st.session_state.suggestions))
    for i, suggestion in enumerate(st.session_state.suggestions):
        if cols[i].button(suggestion, key=f"sugg_{len(st.session_state.messages)}_{i}"):
            selected_suggestion = suggestion

# C. Input Handling
user_input = st.chat_input("iMessage")
if selected_suggestion: user_input = selected_suggestion

if user_input:
    # 1. Append User Message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()

# D. Generation Step
if st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        # Custom IOS Loader
        import random
        loading_text = random.choice(FACTS)
        
        loader_placeholder = st.empty()
        loader_placeholder.markdown(f"""
        <div class="loader-container">
            <div class="loader-dots">
                <div class="dot"></div><div class="dot"></div><div class="dot"></div>
            </div>
            <div class="loader-text" style="font-weight: 500; color: #007AFF;">{loading_text}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # API Call
        history_text = format_history(st.session_state.messages)
        answer, user_opts, sources, videos, lead_data = get_gemini_response(st.session_state.messages[-1]["content"], history_text)
        
        # Remove Loader
        loader_placeholder.empty()
        
        # Process Lead Data & Log
        # Process Lead Data & Log
        tracker.update_from_llm(lead_data)
        
        # Add interaction to conversation log
        tracker.add_interaction(st.session_state.messages[-1]['content'], answer)
        
        full_lead_data = tracker.get_lead_data()
        
        # LOG TO SHEET/CSV (Upsert)
        logger.upsert_lead(full_lead_data)
        
        # Render Answer
        st.markdown(answer)
        
        if sources:
            links_html = '<div class="source-container">'
            for s in sources:
                title = s["title"][:20] + ".." if len(s["title"]) > 20 else s["title"]
                links_html += f'<a href="{s["url"]}" target="_blank" class="source-chip">🔗 {title}</a>'
            links_html += '</div>'
            st.markdown(links_html, unsafe_allow_html=True)

        if videos:
            with st.expander("📺 Watch Videos", expanded=True):
                cols = st.columns(min(len(videos), 2))
                for i, vid_url in enumerate(videos):
                    with cols[i % 2]:
                         if "youtube.com" in vid_url or "youtu.be" in vid_url:
                            st.video(vid_url)

    # Save to History
    st.session_state.messages.append({
        "role": "assistant", 
        "content": answer, 
        "sources": sources,
        "videos": videos
    })
    
    # Update Suggestions
    if user_opts: 
        st.session_state.suggestions = user_opts
    else:
        st.session_state.suggestions = ["Tell me about Loans", "Visa Rules", "Top Universities"]
        
    st.rerun()

