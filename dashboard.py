"""
AI-Powered Customer Support — Streamlit Dashboard
Two portals: Customer (complaint form) and Agent (backend management).
"""
from __future__ import annotations

import os
from pathlib import Path
import requests
import streamlit as st

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BankAssist — Customer Support",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Use DASHBOARD_API_URL env var so Docker can point this at the api service
API_BASE = os.environ.get("DASHBOARD_API_URL", "http://localhost:8000")

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── base ── */
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }

/* ── sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f2044 0%, #1a3a6e 100%);
}
section[data-testid="stSidebar"] * { color: #e8edf5 !important; }
section[data-testid="stSidebar"] .stRadio label { font-size: 0.95rem; }

/* ── hero banner ── */
.hero {
    background: linear-gradient(135deg, #0f2044 0%, #1565c0 100%);
    border-radius: 16px;
    padding: 2.4rem 2.8rem;
    margin-bottom: 2rem;
    color: #fff;
}
.hero h1 { font-size: 2rem; margin: 0 0 .4rem; font-weight: 700; }
.hero p  { font-size: 1rem; margin: 0; opacity: .85; }

/* ── card ── */
.card {
    background: #ffffff;
    border: 1px solid #e2e8f4;
    border-radius: 14px;
    padding: 1.6rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 8px rgba(15,32,68,.07);
}
.card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0f2044;
    margin-bottom: .8rem;
    display: flex;
    align-items: center;
    gap: .45rem;
}

/* ── status pills ── */
.pill {
    display: inline-block;
    padding: .18rem .7rem;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 600;
    letter-spacing: .03em;
}
.pill-open     { background:#dbeafe; color:#1d4ed8; }
.pill-resolved { background:#dcfce7; color:#15803d; }
.pill-pending  { background:#fef9c3; color:#854d0e; }
.pill-discarded{ background:#fee2e2; color:#b91c1c; }

.pill-low    { background:#dcfce7; color:#166534; }
.pill-medium { background:#fef9c3; color:#854d0e; }
.pill-high   { background:#fed7aa; color:#9a3412; }
.pill-urgent { background:#fee2e2; color:#b91c1c; }

/* ── ticket row ── */
.ticket-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: .5rem;
}
.ticket-id   { font-weight: 800; color: #1565c0; font-size: 1.05rem; }
.ticket-subj { font-weight: 600; color: #0f2044; font-size: 1rem; flex: 1; margin: 0 1rem; }

/* ── step indicator ── */
.steps {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.8rem;
}
.step {
    flex: 1;
    text-align: center;
    padding: .7rem;
    border-radius: 10px;
    background: #f0f4ff;
    border: 2px solid #c7d7f5;
    color: #4a6098;
    font-size: .82rem;
    font-weight: 600;
}
.step-active {
    background: #1565c0;
    border-color: #1565c0;
    color: #fff;
}

/* ── success banner ── */
.success-banner {
    background: linear-gradient(135deg,#05966950,#d1fae5);
    border: 1.5px solid #34d399;
    border-radius: 12px;
    padding: 1.4rem 1.8rem;
    margin: 1rem 0;
}
.success-banner h3 { color: #065f46; margin:0 0 .3rem; }
.success-banner p  { color: #047857; margin:0; }

/* ── info strip ── */
.info-strip {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    border-radius: 0 8px 8px 0;
    padding: .7rem 1rem;
    margin: .6rem 0;
    font-size: .88rem;
    color: #1e40af;
}

/* ── metric cards (agent) ── */
.kpi-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.4rem;
    flex-wrap: wrap;
}
.kpi {
    flex: 1;
    min-width: 130px;
    background: #fff;
    border: 1px solid #e2e8f4;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(15,32,68,.06);
}
.kpi-val  { font-size: 1.9rem; font-weight: 800; color: #1565c0; }
.kpi-lbl  { font-size: .75rem; color: #64748b; margin-top: .15rem; }

/* ── divider ── */
.thin-hr { border: none; border-top: 1px solid #e2e8f4; margin: 1rem 0; }

/* ── draft box ── */
.draft-box {
    background: #f8faff;
    border: 1px solid #c7d7f5;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-size: .93rem;
    line-height: 1.65;
    white-space: pre-wrap;
    color: #1e293b;
    margin-bottom: .8rem;
}

/* hide streamlit default chrome */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── API helper ────────────────────────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{API_BASE}{path}", timeout=120, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach the API server (port 8000)."
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            detail = str(e)
        return None, f"HTTP {e.response.status_code}: {detail}"
    except Exception as e:
        return None, str(e)

# ── badge helpers ─────────────────────────────────────────────────────────────
def status_pill(s: str) -> str:
    cls = {"open": "pill-open", "resolved": "pill-resolved",
           "pending": "pill-pending", "discarded": "pill-discarded"}.get(s, "pill-pending")
    return f'<span class="pill {cls}">{s.upper()}</span>'

def priority_pill(p: str) -> str:
    cls = f"pill-{p}"
    icons = {"low": "▼", "medium": "●", "high": "▲", "urgent": "‼"}
    return f'<span class="pill {cls}">{icons.get(p,"")} {p.upper()}</span>'

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏦 BankAssist")
    st.markdown("AI-Powered Customer Support")
    st.markdown("---")

    portal = st.radio(
        "Select Portal",
        ["🙋 Customer Portal", "🛠️ Agent Dashboard"],
        index=0,
    )

    st.markdown("---")
    health, _ = api("GET", "/health")
    if health:
        st.success("API Server: Online")
    else:
        st.error("API Server: Offline")

    st.markdown("---")
    st.caption("API Docs → [localhost:8000/docs](http://localhost:8000/docs)")
    st.caption("v1.0 · AI Support Copilot")


# ═════════════════════════════════════════════════════════════════════════════
# CUSTOMER PORTAL
# ═════════════════════════════════════════════════════════════════════════════
if portal == "🙋 Customer Portal":

    # Hero
    st.markdown("""
    <div class="hero">
        <h1>🏦 BankAssist Support Center</h1>
        <p>Submit your complaint or query and our AI-powered team will respond promptly.</p>
    </div>
    """, unsafe_allow_html=True)

    # Step indicator
    step = st.session_state.get("customer_step", 1)
    st.markdown(f"""
    <div class="steps">
        <div class="step {'step-active' if step == 1 else ''}">① Your Details</div>
        <div class="step {'step-active' if step == 2 else ''}">② Your Complaint</div>
        <div class="step {'step-active' if step == 3 else ''}">③ Confirmation</div>
    </div>
    """, unsafe_allow_html=True)

    if step == 3 and "submitted_ticket" in st.session_state:
        t = st.session_state["submitted_ticket"]
        st.markdown(f"""
        <div class="success-banner">
            <h3>✅ Complaint Submitted Successfully!</h3>
            <p>Your reference number is <strong>#{t['id']}</strong>.
            Our AI support team is reviewing your case and will prepare a response shortly.
            Please save your reference number for future follow-up.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="card">
            <div class="card-title">📋 Submission Summary</div>
            <p><strong>Reference No.:</strong> #{t['id']}</p>
            <p><strong>Name:</strong> {t.get('customer_name') or '—'}</p>
            <p><strong>Email:</strong> {t['customer_email']}</p>
            <p><strong>Subject:</strong> {t['subject']}</p>
            <p><strong>Priority:</strong> {t['priority'].upper()}</p>
            <p><strong>Status:</strong> {t['status'].upper()}</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Submit Another Complaint", type="primary", use_container_width=True):
                for k in ["customer_step", "submitted_ticket", "cust_name", "cust_email", "cust_company"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.info("Keep your reference **#" + str(t['id']) + "** for follow-up.")

    else:
        with st.form("complaint_form", clear_on_submit=False):

            # ── Step 1: Personal details ──────────────────────────────────
            st.markdown('<div class="card"><div class="card-title">👤 Step 1 — Your Personal Details</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                full_name = st.text_input(
                    "Full Name *",
                    placeholder="e.g. Priya Sharma",
                    help="Enter your full name as on bank records",
                )
                email = st.text_input(
                    "Registered Email Address *",
                    placeholder="e.g. priya@gmail.com",
                    help="Use the email linked to your bank account",
                )
            with c2:
                company = st.text_input(
                    "Company / Organisation",
                    placeholder="e.g. Tata Consultancy Services (optional)",
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    '<div class="info-strip">📌 Your email is used to look up your account history for faster resolution.</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Step 2: Complaint details ─────────────────────────────────
            st.markdown('<div class="card"><div class="card-title">📝 Step 2 — Complaint Details</div>', unsafe_allow_html=True)

            category = st.selectbox(
                "Complaint Category *",
                [
                    "Select a category…",
                    "ATM / Cash Withdrawal Issue",
                    "Account Balance / Statement",
                    "KYC / Account Update",
                    "Charges & Fees Query",
                    "Savings Account Rules",
                    "Internet / Mobile Banking",
                    "Card Blocked / Lost",
                    "Loan / EMI Issue",
                    "Other",
                ],
                help="Pick the category that best matches your issue",
            )

            priority = st.select_slider(
                "Urgency Level *",
                options=["low", "medium", "high", "urgent"],
                value="medium",
                help="How urgently do you need this resolved?",
            )

            URGENCY_INFO = {
                "low":    "🟢 Low — We'll respond within 3–5 business days.",
                "medium": "🟡 Medium — We'll respond within 24–48 hours.",
                "high":   "🟠 High — We'll respond within 4–8 hours.",
                "urgent": "🔴 Urgent — We'll respond within 1–2 hours.",
            }
            st.markdown(
                f'<div class="info-strip">{URGENCY_INFO[priority]}</div>',
                unsafe_allow_html=True,
            )

            subject = st.text_input(
                "Subject / Brief Title *",
                placeholder="e.g. ATM deducted money but cash not dispensed",
                max_chars=120,
            )

            description = st.text_area(
                "Describe Your Issue in Detail *",
                placeholder=(
                    "Please describe:\n"
                    "• What happened and when?\n"
                    "• Transaction ID / Account number (if relevant)\n"
                    "• What steps have you already tried?\n"
                    "• Any error messages you saw?"
                ),
                height=200,
            )

            st.markdown(
                '<div class="info-strip">🤖 Our AI will analyse your complaint and generate a personalised response instantly.</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── consent + submit ──────────────────────────────────────────
            consent = st.checkbox(
                "I confirm that the information provided is accurate and I agree to the support terms.",
                value=False,
            )

            submitted = st.form_submit_button(
                "🚀 Submit My Complaint",
                type="primary",
                use_container_width=True,
            )

        # ── validation & API call ─────────────────────────────────────────
        if submitted:
            errors = []
            if not full_name.strip():
                errors.append("Full Name is required.")
            if not email.strip():
                errors.append("Email Address is required.")
            if category == "Select a category…":
                errors.append("Please select a complaint category.")
            if not subject.strip() or len(subject.strip()) < 3:
                errors.append("Subject must be at least 3 characters.")
            if not description.strip() or len(description.strip()) < 10:
                errors.append("Please provide a detailed description (min 10 characters).")
            if not consent:
                errors.append("Please confirm your consent before submitting.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                final_subject = f"[{category}] {subject}" if category != "Select a category…" else subject
                payload = {
                    "customer_email": email.strip(),
                    "customer_name": full_name.strip(),
                    "customer_company": company.strip() or None,
                    "subject": final_subject,
                    "description": description.strip(),
                    "priority": priority,
                    "auto_generate": True,
                }
                with st.spinner("Submitting your complaint and generating AI response…"):
                    result, err = api("POST", "/api/tickets", json=payload)

                if err:
                    st.error(f"Submission failed: {err}")
                else:
                    st.session_state["submitted_ticket"] = result
                    st.session_state["customer_step"] = 3
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# AGENT DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
else:
    st.markdown("""
    <div class="hero">
        <h1>🛠️ Agent Dashboard</h1>
        <p>Manage customer tickets, review AI-generated drafts, and maintain the knowledge base.</p>
    </div>
    """, unsafe_allow_html=True)

    agent_tab = st.tabs(["📥 Ticket Inbox", "📚 Knowledge Base", "🔍 Customer Memory"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — TICKET INBOX
    # ══════════════════════════════════════════════════════════════════════
    with agent_tab[0]:

        # Top bar
        tc1, tc2, tc3 = st.columns([1, 1, 4])
        with tc1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with tc2:
            filter_status = st.selectbox("Filter", ["all", "open", "resolved"], label_visibility="collapsed")

        tickets, err = api("GET", "/api/tickets")
        if err:
            st.error(err)
            st.stop()

        tickets = sorted(tickets or [], key=lambda t: t["id"], reverse=True)
        if filter_status != "all":
            tickets = [t for t in tickets if t["status"] == filter_status]

        # KPI row
        all_tickets, _ = api("GET", "/api/tickets")
        all_tickets = all_tickets or []
        total   = len(all_tickets)
        open_   = sum(1 for t in all_tickets if t["status"] == "open")
        resolved = sum(1 for t in all_tickets if t["status"] == "resolved")
        urgent  = sum(1 for t in all_tickets if t["priority"] == "urgent")

        st.markdown(f"""
        <div class="kpi-row">
            <div class="kpi"><div class="kpi-val">{total}</div><div class="kpi-lbl">Total Tickets</div></div>
            <div class="kpi"><div class="kpi-val" style="color:#1d4ed8">{open_}</div><div class="kpi-lbl">Open</div></div>
            <div class="kpi"><div class="kpi-val" style="color:#15803d">{resolved}</div><div class="kpi-lbl">Resolved</div></div>
            <div class="kpi"><div class="kpi-val" style="color:#b91c1c">{urgent}</div><div class="kpi-lbl">Urgent</div></div>
        </div>
        """, unsafe_allow_html=True)

        if not tickets:
            st.info("No tickets found.")
        else:
            for ticket in tickets:
                tid = ticket["id"]
                with st.expander(
                    f"#{tid}  ·  {ticket['subject'][:70]}",
                    expanded=False,
                ):
                    # Header row with pills
                    st.markdown(
                        f'<div class="ticket-header">'
                        f'<span class="ticket-id">Ticket #{tid}</span>'
                        f'<span class="ticket-subj">{ticket["subject"]}</span>'
                        f'{priority_pill(ticket["priority"])}  {status_pill(ticket["status"])}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('<hr class="thin-hr">', unsafe_allow_html=True)

                    left, right = st.columns([1, 2])

                    with left:
                        st.markdown('<div class="card"><div class="card-title">👤 Customer Info</div>', unsafe_allow_html=True)
                        st.write(f"**Email:** {ticket['customer_email']}")
                        if ticket.get("customer_name"):
                            st.write(f"**Name:** {ticket['customer_name']}")
                        if ticket.get("customer_company"):
                            st.write(f"**Company:** {ticket['customer_company']}")
                        st.markdown("---")
                        st.write(f"**Priority:** {ticket['priority'].upper()}")
                        st.write(f"**Status:** {ticket['status'].upper()}")
                        st.caption(f"Created: {ticket['created_at'][:19].replace('T', ' ')}")
                        st.markdown("</div>", unsafe_allow_html=True)

                        st.markdown('<div class="card"><div class="card-title">📋 Complaint</div>', unsafe_allow_html=True)
                        st.write(ticket["description"])
                        st.markdown("</div>", unsafe_allow_html=True)

                    with right:
                        st.markdown('<div class="card-title">🤖 AI Draft Reply</div>', unsafe_allow_html=True)

                        draft, derr = api("GET", f"/api/drafts/{tid}")

                        if derr and "404" in derr:
                            st.info("No draft generated yet.")
                            if st.button("Generate AI Draft", key=f"gen_{tid}", type="primary"):
                                with st.spinner("Generating AI draft…"):
                                    result, gerr = api("POST", f"/api/tickets/{tid}/generate-draft")
                                if gerr:
                                    st.error(gerr)
                                else:
                                    st.success("Draft generated!")
                                    st.rerun()
                        elif derr:
                            st.error(derr)
                        else:
                            draft_id = draft["id"]
                            ctx      = draft.get("context_used") or {}
                            signals  = ctx.get("signals") or {}

                            # AI signal metrics
                            if signals:
                                m1, m2, m3, m4 = st.columns(4)
                                m1.metric("Memory Hits",    signals.get("memory_hit_count", 0))
                                m2.metric("KB Hits",        signals.get("knowledge_hit_count", 0))
                                m3.metric("Tool Calls",     signals.get("tool_call_count", 0))
                                m4.metric("Draft Status",   draft.get("status", "—").upper())
                                sources = signals.get("knowledge_sources") or []
                                if sources:
                                    st.caption("📄 Sources: " + " · ".join(sources))

                            st.markdown("<br>", unsafe_allow_html=True)

                            # Editable draft
                            edited_content = st.text_area(
                                "Edit draft before actioning:",
                                value=draft["content"],
                                height=280,
                                key=f"content_{draft_id}",
                            )

                            b1, b2, b3, b4 = st.columns(4)
                            with b1:
                                if st.button("✅ Accept", key=f"acc_{draft_id}", type="primary", use_container_width=True):
                                    _, uerr = api("PATCH", f"/api/drafts/{draft_id}",
                                                  json={"content": edited_content, "status": "accepted"})
                                    if uerr:
                                        st.error(uerr)
                                    else:
                                        st.success("Accepted — ticket resolved.")
                                        st.rerun()
                            with b2:
                                if st.button("💾 Save", key=f"sav_{draft_id}", use_container_width=True):
                                    _, uerr = api("PATCH", f"/api/drafts/{draft_id}",
                                                  json={"content": edited_content})
                                    if uerr:
                                        st.error(uerr)
                                    else:
                                        st.success("Saved.")
                            with b3:
                                if st.button("🔄 Regenerate", key=f"regen_{tid}", use_container_width=True):
                                    with st.spinner("Regenerating…"):
                                        result, gerr = api("POST", f"/api/tickets/{tid}/generate-draft")
                                    if gerr:
                                        st.error(gerr)
                                    else:
                                        st.success("New draft ready.")
                                        st.rerun()
                            with b4:
                                if st.button("🗑️ Discard", key=f"dis_{draft_id}", use_container_width=True):
                                    _, uerr = api("PATCH", f"/api/drafts/{draft_id}",
                                                  json={"status": "discarded"})
                                    if uerr:
                                        st.error(uerr)
                                    else:
                                        st.warning("Discarded.")
                                        st.rerun()

                            # Tool call trace
                            tool_calls = ctx.get("tool_calls") or []
                            if tool_calls:
                                with st.expander("🔧 Tool Call Trace"):
                                    for tc in tool_calls:
                                        st.markdown(
                                            f"**{tc.get('tool_name')}** "
                                            f"— `{tc.get('status')}`"
                                        )
                                        if tc.get("output_text"):
                                            st.code(tc["output_text"], language="text")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — KNOWLEDGE BASE
    # ══════════════════════════════════════════════════════════════════════
    with agent_tab[1]:
        st.markdown("### 📚 Knowledge Base Management")
        st.markdown(
            "Index the Markdown documents in `knowledge_base/` into the ChromaDB vector store. "
            "The AI uses these documents to answer customer queries accurately."
        )

        kb_dir   = Path(__file__).parent / "knowledge_base"
        md_files = sorted(kb_dir.glob("*.md")) if kb_dir.exists() else []

        if md_files:
            st.markdown("**Documents available for indexing:**")
            for f in md_files:
                size_kb = round(f.stat().st_size / 1024, 1)
                st.markdown(f"📄 `{f.name}` &nbsp; <span style='color:#64748b;font-size:.82rem'>({size_kb} KB)</span>", unsafe_allow_html=True)
        else:
            st.warning("No `.md` files found in `knowledge_base/`.")

        st.markdown("---")
        clear = st.checkbox("Clear existing index before re-ingesting", value=False)

        if st.button("🚀 Ingest Knowledge Base", type="primary", use_container_width=False):
            with st.spinner("Ingesting documents into vector store…"):
                result, err = api("POST", "/api/knowledge/ingest", json={"clear_existing": clear})
            if err:
                st.error(err)
            else:
                st.success(
                    f"Ingestion complete!  \n"
                    f"Files indexed: **{result['files_indexed']}** · "
                    f"Chunks: **{result['chunks_indexed']}** · "
                    f"Collection size: **{result['collection_count']}**"
                )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — CUSTOMER MEMORY
    # ══════════════════════════════════════════════════════════════════════
    with agent_tab[2]:
        st.markdown("### 🔍 Customer Memory Lookup")
        st.markdown("Retrieve past resolutions and customer-specific memory stored by the AI.")

        mem_email = st.text_input("Customer Email", placeholder="customer@example.com", key="mem_email")

        col_a, col_b = st.columns([1, 3])
        with col_a:
            lookup = st.button("Fetch Memories", type="primary", use_container_width=True)

        if lookup and mem_email.strip():
            # First get customer ID by listing tickets and matching email
            tickets_all, terr = api("GET", "/api/tickets")
            if terr:
                st.error(terr)
            else:
                match = next(
                    (t for t in (tickets_all or []) if t["customer_email"].lower() == mem_email.strip().lower()),
                    None,
                )
                if not match:
                    st.warning("No tickets found for that email address.")
                else:
                    cid = match["customer_id"]
                    mems, merr = api("GET", f"/api/customers/{cid}/memories")
                    if merr:
                        st.error(merr)
                    else:
                        memories = mems.get("memories") or []
                        st.markdown(f"**Customer ID:** {cid}  |  **Memories stored:** {len(memories)}")
                        if not memories:
                            st.info("No memories stored yet for this customer.")
                        else:
                            for i, mem in enumerate(memories, 1):
                                with st.expander(f"Memory {i}"):
                                    st.json(mem)

                        # Memory search
                        st.markdown("---")
                        st.markdown("**Search Customer Memories**")
                        sq1, sq2 = st.columns([3, 1])
                        with sq1:
                            search_q = st.text_input("Search query", placeholder="e.g. ATM withdrawal issue", key="mem_search")
                        with sq2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            do_search = st.button("Search", key="do_mem_search")

                        if do_search and search_q.strip():
                            res, serr = api(
                                "GET",
                                f"/api/customers/{cid}/memory-search",
                                params={"query": search_q.strip(), "limit": 10},
                            )
                            if serr:
                                st.error(serr)
                            else:
                                results = res.get("results") or []
                                if not results:
                                    st.info("No matching memories found.")
                                else:
                                    for r in results:
                                        st.markdown(f"- {r}")
