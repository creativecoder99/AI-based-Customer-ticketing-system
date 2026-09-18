import os
import requests
import streamlit as st

# Configure Streamlit page
st.set_page_config(
    page_title="Maxsorlabs | AI Decision Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API endpoint configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

# Initialize session state variables
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "New Decision"


# Inject Modern Design CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
        padding: 24px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(49, 46, 129, 0.2);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    .main-header p {
        margin: 6px 0 0 0;
        color: #c7d2fe;
        font-size: 14px;
    }
    
    .status-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 20px;
    }
    
    .action-badge {
        display: inline-block;
        padding: 6px 14px;
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.5px;
        border-radius: 9999px;
        text-transform: uppercase;
    }
    
    .badge-REQUEST_PHOTOS { background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
    .badge-APPROVE_REFUND { background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
    .badge-APPROVE_RETURN { background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
    .badge-REJECT_REQUEST { background-color: #ffe4e6; color: #9f1239; border: 1px solid #fecdd3; }
    .badge-EXPEDITE_SHIPPING { background-color: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; }
    .badge-NEEDS_MORE_INFORMATION { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
    
    .decision-container {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 24px;
        margin-top: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    .source-tag {
        display: inline-block;
        background: #f1f5f9;
        color: #475569;
        font-size: 12px;
        font-weight: 500;
        padding: 3px 10px;
        border-radius: 6px;
        margin-right: 6px;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


def check_api_health():
    """Verify connectivity with the FastAPI backend."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=2)
        if resp.status_code == 200:
            return True, resp.json()
    except Exception:
        pass
    return False, {}


def get_auth_headers():
    """Return Bearer authorization headers if token is present."""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


# Render App Banner
st.markdown("""
<div class="main-header">
    <h1>🛡️ Support Ticket Decision Assistant</h1>
    <p>Minimal AI Decision API powered by FastAPI, SQLite, RAG, and Gemini LLM</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ System Status")
    is_healthy, health_info = check_api_health()
    if is_healthy:
        st.success(f"Backend Online ({health_info.get('rag_chunks_loaded', 0)} RAG chunks)")
    else:
        st.error("Backend Disconnected")
        st.caption(f"Make sure FastAPI is running on `{API_URL}`.")
        st.code("uvicorn src.api:app --reload")

    st.markdown("---")
    st.markdown("### 👤 User Session")
    if st.session_state.user:
        st.markdown(f"**Logged in as:**\n`{st.session_state.user.get('email')}`")
        st.caption(f"User ID: {st.session_state.user.get('id')}")
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()
    else:
        st.info("Not authenticated. Please Log In or Register.")


# Main Application Navigation Tabs
tab_decision, tab_history, tab_auth = st.tabs([
    "⚡ New Decision",
    "📋 Ticket History",
    "🔐 Login / Register"
])


# ==========================================
# TAB 1: NEW DECISION
# ==========================================
with tab_decision:
    st.subheader("Submit Customer Support Ticket")
    st.markdown("Enter a customer support request below to run policy retrieval and generate a grounded AI decision.")

    if not st.session_state.token:
        st.warning("⚠️ You must be logged in to submit tickets and view AI recommendations.")
        st.info("Head over to the **🔐 Login / Register** tab to sign in or create an account.")
    else:
        # Predefined scenario selector for quick demo
        st.markdown("**Quick Preset Scenarios:**")
        preset_cols = st.columns([1, 1, 1, 1])
        selected_preset = None

        with preset_cols[0]:
            if st.button("📦 High-Value Damaged (₹4,500)", use_container_width=True):
                selected_preset = "I received my ₹4,500 ceramic dinner set yesterday, but the bowls arrived completely shattered inside the box. How do I proceed?"
        with preset_cols[1]:
            if st.button("☕ Low-Value Damaged (₹450)", use_container_width=True):
                selected_preset = "My delivery arrived 3 hours ago with a chipped coffee mug worth ₹450. I would like a refund please."
        with preset_cols[2]:
            if st.button("👟 Late Return (42 Days)", use_container_width=True):
                selected_preset = "I bought running shoes delivered 42 days ago. I realized I don't use them and want to return them."
        with preset_cols[3]:
            if st.button("🚚 Lost Shipment (8 Days)", use_container_width=True):
                selected_preset = "My courier tracking has had zero scan updates or movement for the past 8 consecutive business days. It seems stuck."

        default_msg = selected_preset or ""
        ticket_input = st.text_area(
            "Customer Ticket Message",
            value=default_msg,
            height=120,
            placeholder="Type customer message here (e.g. 'My ₹4,500 dinner set arrived damaged yesterday...')"
        )

        col_btn, _ = st.columns([1, 4])
        with col_btn:
            submit_btn = st.button("🚀 Analyze & Generate Decision", type="primary", use_container_width=True)

        if submit_btn:
            if not ticket_input.strip():
                st.error("Please provide a ticket message.")
            else:
                with st.spinner("Retrieving relevant policy documents and generating AI decision..."):
                    try:
                        resp = requests.post(
                            f"{API_URL}/tickets",
                            headers=get_auth_headers(),
                            json={"message": ticket_input.strip()},
                            timeout=15
                        )
                        if resp.status_code == 201:
                            data = resp.json()
                            dec = data.get("decision", {})
                            action = dec.get("action", "NEEDS_MORE_INFORMATION")
                            conf = dec.get("confidence", 0.0)
                            reason = dec.get("reason", "No reason provided.")
                            sources = dec.get("sources", [])

                            st.success("Decision generated and persisted to database!")

                            # Decision Card
                            badge_class = f"badge-{action}"
                            sources_html = "".join([f'<span class="source-tag">📄 {s}</span>' for s in sources])

                            st.markdown(f"""
                            <div class="decision-container">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                                    <div>
                                        <span class="action-badge {badge_class}">{action}</span>
                                        <span style="color: #64748b; font-size: 13px; margin-left: 12px;">Ticket #{data.get('id')}</span>
                                    </div>
                                    <div style="font-weight: 600; color: #334155;">
                                        Confidence: <strong>{int(conf * 100)}%</strong>
                                    </div>
                                </div>
                                <div style="margin-bottom: 16px;">
                                    <div style="font-size: 13px; color: #64748b; font-weight: 500; margin-bottom: 4px;">POLICY REASONING</div>
                                    <div style="color: #1e293b; font-size: 15px; line-height: 1.6;">{reason}</div>
                                </div>
                                <div>
                                    <div style="font-size: 13px; color: #64748b; font-weight: 500; margin-bottom: 6px;">GROUNDED SOURCES</div>
                                    <div>{sources_html}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Progress bar for confidence
                            st.progress(conf)

                            with st.expander("🔍 Inspect Full JSON Payload"):
                                st.json(data)
                        elif resp.status_code == 401:
                            st.error("Session expired or invalid. Please log in again.")
                            st.session_state.token = None
                            st.session_state.user = None
                        else:
                            st.error(f"Error {resp.status_code}: {resp.text}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Failed to connect to API server: {str(e)}")


# ==========================================
# TAB 2: HISTORY
# ==========================================
with tab_history:
    st.subheader("Your Submitted Tickets & Decisions")

    if not st.session_state.token:
        st.warning("Please log in to view your ticket history.")
    else:
        col_ref, _ = st.columns([1, 5])
        with col_ref:
            refresh_history = st.button("🔄 Refresh History")

        try:
            resp = requests.get(f"{API_URL}/tickets", headers=get_auth_headers(), timeout=10)
            if resp.status_code == 200:
                tickets = resp.json()
                if not tickets:
                    st.info("No tickets submitted yet. Submit your first ticket in the 'New Decision' tab!")
                else:
                    st.write(f"Showing **{len(tickets)}** ticket(s):")
                    for t in tickets:
                        dec = t.get("decision") or {}
                        act = dec.get("action", "PENDING")
                        badge_class = f"badge-{act}"

                        with st.expander(f"Ticket #{t['id']} — {act} ({t['created_at'][:19].replace('T', ' ')})"):
                            st.markdown(f"**Customer Message:**\n> {t['message']}")

                            if dec:
                                st.markdown("---")
                                col_d1, col_d2 = st.columns([1, 3])
                                with col_d1:
                                    st.markdown(f'<span class="action-badge {badge_class}">{act}</span>', unsafe_allow_html=True)
                                    st.write(f"**Confidence:** {int(dec.get('confidence', 0) * 100)}%")
                                with col_d2:
                                    st.markdown(f"**Reasoning:** {dec.get('reason')}")
                                    srcs = dec.get("sources", [])
                                    if srcs:
                                        src_tags = " ".join([f"`{s}`" for s in srcs])
                                        st.markdown(f"**Sources:** {src_tags}")

                            # Button to inspect single ticket via GET /tickets/{id}
                            if st.button(f"🔎 Fetch via API /tickets/{t['id']}", key=f"fetch_{t['id']}"):
                                single_resp = requests.get(
                                    f"{API_URL}/tickets/{t['id']}",
                                    headers=get_auth_headers()
                                )
                                if single_resp.status_code == 200:
                                    st.json(single_resp.json())
                                else:
                                    st.error(single_resp.text)
            elif resp.status_code == 401:
                st.error("Authentication expired. Please log in again.")
            else:
                st.error(f"Error fetching tickets: {resp.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to communicate with API: {str(e)}")


# ==========================================
# TAB 3: LOGIN / REGISTER
# ==========================================
with tab_auth:
    auth_mode = st.radio("Choose Action", ["Log In", "Register"], horizontal=True)

    if auth_mode == "Log In":
        st.subheader("Account Login")
        with st.form("login_form"):
            login_email = st.text_input("Email Address", placeholder="alice@example.com")
            login_password = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Log In", type="primary")

            if submit_login:
                if not login_email or not login_password:
                    st.error("Please provide both email and password.")
                else:
                    try:
                        resp = requests.post(
                            f"{API_URL}/login",
                            json={"email": login_email.strip(), "password": login_password}
                        )
                        if resp.status_code == 200:
                            token_data = resp.json()
                            token = token_data.get("access_token")
                            st.session_state.token = token

                            # Fetch /me
                            me_resp = requests.get(
                                f"{API_URL}/me",
                                headers={"Authorization": f"Bearer {token}"}
                            )
                            if me_resp.status_code == 200:
                                st.session_state.user = me_resp.json()
                            st.success(f"Welcome back, {login_email}! You are now logged in.")
                            st.rerun()
                        else:
                            st.error(resp.json().get("detail", "Login failed."))
                    except Exception as e:
                        st.error(f"Could not connect to backend: {str(e)}")

    else:
        st.subheader("Create New Account")
        with st.form("register_form"):
            reg_email = st.text_input("Email Address", placeholder="bob@example.com")
            reg_password = st.text_input("Password (min 6 characters)", type="password", placeholder="••••••••")
            reg_password_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")
            submit_register = st.form_submit_button("Register Account", type="primary")

            if submit_register:
                if not reg_email or not reg_password:
                    st.error("Please fill in all fields.")
                elif reg_password != reg_password_confirm:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    try:
                        resp = requests.post(
                            f"{API_URL}/register",
                            json={"email": reg_email.strip(), "password": reg_password}
                        )
                        if resp.status_code == 201:
                            st.success("Account created successfully! You may now log in.")
                        else:
                            st.error(resp.json().get("detail", "Registration failed."))
                    except Exception as e:
                        st.error(f"Could not connect to backend: {str(e)}")
