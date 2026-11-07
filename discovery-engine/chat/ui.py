"""Chat window for the SIP instalment recovery screen."""

import re

import streamlit as st
from streamlit.errors import StreamlitAPIException

from chat.handoff import new_ticket_id, summary, support_link
from chat.pipeline import apply_streaks, run_turn
from chat.safety import mask
from chat.language import detect_language, safety_text
from chat.screen_agent import decide

HELP_ACTIONS = {"answer", "fallback", "none"}
UNSURE_ACTIONS = {"fallback", "limited", "decline"}
WHY_RE = re.compile(
    r"\bwhy\b.{0,60}\b(fail|failed|didn't|did not|reject|declin|payment|debit)\b"
    r"|\b(payment|debit|instalment|installment)\b.{0,30}\b(fail|failed)\b",
    re.I,
)


def ensure_state():
    defaults = {
        "chat": [],
        "chat_state": "ASKING",
        "chat_open": False,
        "not_yet_count": 0,
        "low_streak": 0,
        "decline_streak": 0,
        "form_i": 0,
        "pending_question": None,
        "handoff_reason": "",
        "last_user_masked": "",
        "last_agent": "",
        "kb_titles": [],
        "ticket_id": "",
        "screen_offer": None,
        "chat_archive": [],
        "active_chat_id": "",
        "show_history": False,
        "support_sent": False,
        "person_chat": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def page_context():
    return {
        "screen": "instalment_recovery",
        "scenario": st.session_state.get("scenario") or "",
        "autopay_state": st.session_state.get("autopay_state") or "",
        "sip_amount": 2000,
        "debit_day": 5,
        "values": "sample",
    }


def _opener(scenario):
    return "Hi, what can I help you with?"


def ensure_opener():
    scenario = st.session_state.get("scenario") or ""
    chat = st.session_state.chat
    text = _opener(scenario)
    if not chat:
        chat.append({"role": "assistant", "text": text, "action": "opener"})
        return
    has_user = any(item.get("role") == "user" for item in chat)
    if not has_user and chat[0].get("action") == "opener":
        chat[0]["text"] = text


def _remember(result, masked):
    st.session_state.last_user_masked = masked
    st.session_state.last_agent = result.get("agent") or ""
    titles = list(st.session_state.get("kb_titles") or [])
    for title in result.get("kb_titles") or []:
        if title and title not in titles:
            titles.append(title)
    st.session_state.kb_titles = titles
    if result.get("reason"):
        st.session_state.handoff_reason = result["reason"]


def handle_question(text, from_clarifier=False):
    try:
        _handle_question(text, from_clarifier)
    finally:
        _snapshot()


def _handle_question(text, from_clarifier=False):
    masked, changed = mask(text)
    language = detect_language(masked)
    st.session_state.chat_language = language
    st.session_state.chat.append({"role": "user", "text": masked, "action": "user"})
    if changed:
        st.session_state.chat.append(
            {"role": "assistant", "text": safety_text(language, "mask"), "action": "note"}
        )
    if not from_clarifier:
        st.session_state.not_yet_count = 0
        st.session_state.support_prompt = False
    if WHY_RE.search(masked):
        st.session_state.chat.append(
            {
                "role": "assistant",
                "text": (
                    "The payment didn't go through when the bank did not accept the debit, "
                    "or when autopay did not send it. "
                    "Check that the balance covers ₹2,000, and that UPI autopay is on. "
                    "UPI autopay is your permission for the bank to send the instalment each month."
                ),
                "action": "answer",
            }
        )
        st.session_state.chat_state = "ANSWERED"
        return
    decision = decide(masked, st.session_state.get("screen_offer"), page_context().get("scenario"))
    if _take_screen(decision):
        return
    with st.spinner("Checking the notes..."):
        result = run_turn(masked, page_context())
    result, low_streak, decline_streak = apply_streaks(
        result,
        st.session_state.low_streak,
        st.session_state.decline_streak,
    )
    st.session_state.low_streak = low_streak
    st.session_state.decline_streak = decline_streak
    _remember(result, masked)
    action = result["action"]
    if action == "handoff":
        st.session_state.chat_state = "HANDOFF"
        st.session_state.handoff_reason = result.get("reason") or "user asked for support"
        return
    if result.get("text"):
        st.session_state.chat.append(
            {
                "role": "assistant",
                "text": result["text"],
                "action": action,
                "source_title": result.get("source_title") or "",
                "source_url": result.get("source_url") or "",
                "clarifiers": result.get("clarifiers") or [],
            }
        )
    if action in UNSURE_ACTIONS:
        st.session_state.chat_state = "ANSWERED"
    elif action in HELP_ACTIONS:
        st.session_state.chat_state = "ANSWERED"
        st.session_state.clarifiers = result.get("clarifiers") or []
    else:
        st.session_state.chat_state = "ASKING"


def _on_yes():
    st.session_state.chat_state = "RESOLVED"
    st.session_state.not_yet_count = 0


def _on_else():
    st.session_state.chat_state = "ASKING"
    st.session_state.not_yet_count = 0


def _on_support():
    st.session_state.chat_state = "HANDOFF"
    st.session_state.handoff_reason = "user asked for support"


def _on_person():
    """Start a support chat. The request form stays hidden until they ask for it."""
    st.session_state.person_chat = True
    st.session_state.chat_state = "ASKING"
    st.session_state.support_prompt = False
    last = ""
    if st.session_state.chat:
        last = st.session_state.chat[-1].get("text") or ""
    if last != "What can I help you with?":
        st.session_state.chat.append(
            {
                "role": "assistant",
                "text": "What can I help you with?",
                "action": "person",
            }
        )


def _on_call():
    st.session_state.chat.append(
        {
            "role": "assistant",
            "text": (
                "You can call a support agent from Help in the Groww app. "
                "This demo cannot place a call."
            ),
            "action": "note",
        }
    )
    st.session_state.chat_state = "ASKING"
    st.session_state.support_prompt = False


def _mark_closed():
    if st.session_state.get("keep_chat"):
        st.session_state.chat_open = True
        return
    st.session_state.chat_open = False


def _take_screen(decision):
    if decision["type"] == "clear":
        st.session_state.screen_offer = None
        st.session_state.chat.append(
            {"role": "assistant", "text": decision["text"], "action": "screen"}
        )
        st.session_state.chat_state = "ASKING"
        return True
    if decision["type"] == "offer":
        st.session_state.screen_offer = decision["offer"]
        st.session_state.chat.append(
            {"role": "assistant", "text": decision["text"], "action": "screen"}
        )
        st.session_state.chat_state = "ASKING"
        return True
    if decision["type"] == "apply":
        _apply_screen(decision)
        return True
    return False


def _screen_buttons():
    offer = st.session_state.get("screen_offer")
    if not offer:
        return
    yes_col, no_col = st.columns(2)
    with yes_col:
        with st.container(key="screen_yes_wrap"):
            st.button(
                "Yes, do it",
                key="screen_yes",
                type="primary",
                on_click=_queue,
                args=("yes", False),
            )
    with no_col:
        st.button("Not now", key="screen_no", on_click=_queue, args=("no", False))


def _apply_screen(decision):
    st.session_state.chat.append(
        {"role": "assistant", "text": decision["text"], "action": "screen"}
    )
    st.session_state.screen_offer = decision.get("offer")
    st.session_state.pending_situation = decision["situation"]
    st.session_state.pending_step = decision["step"]
    st.session_state.sip_amount_label = decision["amount"]
    st.session_state.sip_bank_label = decision["bank"]
    st.session_state.filled_by_chat = True
    st.session_state.chat_state = "ASKING"
    st.session_state.keep_chat = True
    st.session_state.chat_open = True
    st.rerun()


def _queue(text, from_clarifier):
    st.session_state.pending_question = {"text": text, "from_clarifier": from_clarifier}


def _send_support():
    if not st.session_state.get("ticket_id"):
        st.session_state.ticket_id = new_ticket_id()
    st.session_state.support_sent = True


def _bubble(item, show_help):
    role = "user" if item.get("role") == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(item.get("text") or "")
        if role == "assistant":
            title = item.get("source_title") or ""
            url = item.get("source_url") or ""
            if title:
                if url:
                    st.markdown("Source: [" + title + "](" + url + ")")
                else:
                    st.markdown("Source: " + title)
            if show_help:
                st.markdown("Are you satisfied with the response?")
                st.button("Yes", key="help_yes", on_click=_on_yes)
                st.button(
                    "No, connect me with support",
                    key="help_no",
                    on_click=_on_call,
                )


def _retry_box():
    st.markdown("Sorry that did not solve it. Which is closest?")
    options = list(st.session_state.get("clarifiers") or [])
    for index, label in enumerate(options):
        st.button(
            label,
            key="clarifier_" + str(index),
            on_click=_queue,
            args=(label, True),
        )
    st.button("Something else", key="something_else", on_click=_on_else)


def _resolved_box():
    st.markdown("Glad it helped. Anything else?")
    st.button("Done", key="chat_done", on_click=_new_chat)


def _handoff_card():
    text = summary(
        st.session_state.get("scenario"),
        st.session_state.get("last_user_masked") or "",
        st.session_state.get("last_agent") or "",
        st.session_state.get("kb_titles") or [],
        st.session_state.get("handoff_reason") or "user asked for support",
    )
    st.markdown("**Support request**")
    st.code(text)
    st.button("Send", key="send_support", on_click=_send_support)
    if st.session_state.get("support_sent"):
        st.markdown("Sent. Request " + st.session_state.ticket_id + ".")
        st.markdown("Demo: no support person receives this.")
        link = support_link()
        if link:
            st.markdown("[Official support page](" + link + ")")


def _read_form():
    form_key = "sip_help_form_" + str(st.session_state.form_i)
    has_user = any(item.get("role") == "user" for item in st.session_state.chat)
    placeholder = "Ask about your instalment"
    with st.form(form_key, clear_on_submit=True):
        text = st.text_input("Your question", placeholder=placeholder)
        sent = st.form_submit_button("Send")
    if sent and (text or "").strip():
        return text.strip()
    return ""


def _draw_history():
    chat = st.session_state.chat
    last_assistant = -1
    for index, item in enumerate(chat):
        if item.get("role") == "assistant":
            last_assistant = index
    for index, item in enumerate(chat):
        show_help = (
            st.session_state.chat_state == "ANSWERED"
            and index == last_assistant
            and item.get("action") in (UNSURE_ACTIONS | {"answer"})
        )
        _bubble(item, show_help)


EXAMPLES = (
    ("Why did it fail?", "Why didn't this instalment go through?"),
    ("How do I read my SIP chart?", "How do I read my SIP chart?"),
    ("How does a SIP work?", "How does a SIP work?"),
    ("I pay it myself", "I have been paying this SIP manually"),
)


def _example_row():
    if st.session_state.chat_state == "HANDOFF":
        return
    left, right = st.columns(2)
    for index, (label, text) in enumerate(EXAMPLES):
        column = left if index % 2 == 0 else right
        with column:
            st.button(label, key="example_" + str(index), on_click=_queue, args=(text, False))


def _chat_title(messages):
    for item in messages:
        if item.get("role") == "user" and (item.get("text") or "").strip():
            text = item["text"].strip()
            if len(text) > 42:
                return text[:42] + "…"
            return text
    return "Chat"


def _snapshot():
    messages = [dict(item) for item in st.session_state.chat]
    if not any(item.get("role") == "user" for item in messages):
        return
    archive = st.session_state.chat_archive
    title = _chat_title(messages)
    active = st.session_state.get("active_chat_id") or ""
    for row in archive:
        if row["id"] == active:
            row["title"] = title
            row["messages"] = messages
            return
    chat_id = "c" + str(len(archive) + 1)
    archive.insert(0, {"id": chat_id, "title": title, "messages": messages})
    st.session_state.active_chat_id = chat_id


def _reset_chat():
    st.session_state.chat = []
    st.session_state.chat_state = "ASKING"
    st.session_state.screen_offer = None
    st.session_state.not_yet_count = 0
    st.session_state.low_streak = 0
    st.session_state.decline_streak = 0
    st.session_state.form_i = int(st.session_state.get("form_i") or 0) + 1
    st.session_state.support_prompt = False
    st.session_state.ticket_id = ""
    st.session_state.support_sent = False
    st.session_state.handoff_reason = ""
    st.session_state.person_chat = False


def _new_chat():
    _snapshot()
    _reset_chat()
    st.session_state.active_chat_id = ""
    st.session_state.show_history = False


def _toggle_history():
    opening = not st.session_state.get("show_history")
    if opening:
        _snapshot()
    st.session_state.show_history = opening


def _open_saved(chat_id):
    _snapshot()
    for row in st.session_state.chat_archive:
        if row["id"] != chat_id:
            continue
        st.session_state.chat = [dict(item) for item in row["messages"]]
        st.session_state.active_chat_id = chat_id
        st.session_state.chat_state = "ASKING"
        st.session_state.screen_offer = None
        st.session_state.show_history = False
        st.session_state.form_i = int(st.session_state.get("form_i") or 0) + 1
        return


def _chat_tools():
    new_col, hist_col = st.columns(2)
    with new_col:
        st.button("New chat", key="new_chat", on_click=_new_chat)
    with hist_col:
        st.button("Chat history", key="chat_history", on_click=_toggle_history)


def _history_list():
    rows = st.session_state.chat_archive
    st.markdown("**Earlier chats**")
    if not rows:
        st.markdown("No earlier chats yet. Send a question, then it shows up here.")
        return
    active = st.session_state.get("active_chat_id") or ""
    for index, row in enumerate(rows):
        if index:
            st.divider()
        heading = row["title"]
        if row["id"] == active:
            heading = heading + " · this chat"
        st.markdown("**" + heading + "**")
        for item in row["messages"]:
            text = item.get("text") or ""
            if not text:
                continue
            role = "user" if item.get("role") == "user" else "assistant"
            with st.chat_message(role):
                st.markdown(text)
        if row["id"] != active:
            st.button("Open this chat", key="hist_" + row["id"], on_click=_open_saved, args=(row["id"],))


def _draw_controls():
    state = st.session_state.chat_state
    if state == "RETRY":
        _retry_box()
    if state == "RESOLVED":
        _resolved_box()
    if state == "HANDOFF":
        _handoff_card()


def render_panel():
    ensure_state()
    ensure_opener()
    pending = st.session_state.get("pending_question")
    if pending:
        st.session_state.pending_question = None
        handle_question(pending["text"], from_clarifier=pending.get("from_clarifier"))

    title_col, _gap, tools_col = st.columns([1.45, 0.28, 1.15], vertical_alignment="center")
    with title_col:
        st.markdown(
            "<p class='panel-title'>Ask the SIP helper</p>"
            "<p class='panel-sub'>About your instalment or how SIPs work.</p>",
            unsafe_allow_html=True,
        )
    with tools_col:
        with st.container(key="chat_tools"):
            _chat_tools()
    history_key = "sip_help_archive" if st.session_state.get("show_history") else "sip_help_history"
    history_slot = st.container(key=history_key)
    actions = st.container(key="sip_help_actions")
    lower = st.container(key="sip_help_lower")
    submitted = ""
    with lower:
        _example_row()
        if st.session_state.chat_state != "HANDOFF":
            submitted = _read_form()
        _draw_controls()
    if submitted:
        st.session_state.not_yet_count = 0
        handle_question(submitted, from_clarifier=False)
        st.session_state.form_i += 1
    with history_slot:
        if st.session_state.get("show_history"):
            _history_list()
        else:
            _draw_history()
            import streamlit.components.v1 as components
            components.html(
                """
                <script>
                  const box = window.parent.document.querySelector('.st-key-sip_help_history');
                  if (box) { box.scrollTop = box.scrollHeight; }
                </script>
                """,
                height=0,
            )
    with actions:
        _screen_buttons()
    if submitted:
        try:
            st.rerun(scope="fragment")
        except StreamlitAPIException:
            return


def mount():
    with st.container(key="sip_panel"):
        render_panel()
