"""SIP instalment recovery prototype.

A clickable screen for one monthly SIP when this month's instalment did not finish.
No payment is sent. Nothing is written to the comment files.

Analysis of public comments. Not investment advice.
"""

import html
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AMOUNT = "₹2,000"
BANK = "bank account ending 4821"
NEXT_DATE = "5 December"
OPEN_MONTH = "November"

SITUATIONS = [
    {
        "label": "Bank rejected the debit",
        "kind": "pay",
        "status": "Did not go through",
        "tone": "warn",
        "lead": "The bank rejected the debit. The balance was available.",
        "next": "This SIP is still set up. The next debit date is {next_date}.",
    },
    {
        "label": "Autopay did not send it",
        "kind": "pay",
        "status": "Still pending",
        "tone": "warn",
        "lead": "Autopay did not send the November instalment.",
        "next": "It stays pending until this month is paid. The SIP amount does not change.",
    },
    {
        "label": "Money already left the bank",
        "kind": "status",
        "status": "Money received · units pending",
        "tone": "wait",
        "lead": "We have the {month} amount. Units are not allotted yet. They should appear by 7 November.",
        "next": (
            "If allotment will not happen, the {amount} goes back to the {bank}. "
            "There is no second payment."
        ),
    },
    {
        "label": "UPI autopay is off before the debit day",
        "kind": "renew",
        "status": "Autopay is off",
        "tone": "wait",
        "lead": "{next_date}'s debit cannot be sent. UPI autopay for this SIP is not active.",
        "next": "The SIP stays {amount} on the 5th. Renewing autopay lets that debit be sent.",
    },
    {
        "label": "Bank change",
        "kind": "bank",
        "status": "Bank needs an update",
        "tone": "wait",
        "lead": "This SIP still debits the {bank}.",
        "next": "A bank change switches the account. The SIP amount stays {amount}.",
    },
]


def facts():
    amount = st.session_state.get("sip_amount_label") or AMOUNT
    bank = st.session_state.get("sip_bank_label") or BANK
    next_date = st.session_state.get("sip_next_date") or NEXT_DATE
    return {"amount": amount, "bank": bank, "next_date": next_date, "month": OPEN_MONTH}


def with_facts(item):
    data = facts()
    copy = dict(item)
    copy["lead"] = item["lead"].format(**data)
    copy["next"] = item["next"].format(**data)
    return copy


def apply_agent_screen():
    """Apply a screen change the chat stored on the previous run, before widgets exist."""
    label = st.session_state.pop("pending_situation", None)
    step = st.session_state.pop("pending_step", None)
    if label:
        st.session_state.situation = label
    if step:
        st.session_state.step = step
        st.session_state.agent_set_step = True


def situation_by_label(label):
    for item in SITUATIONS:
        if item["label"] == label:
            return item
    return SITUATIONS[0]


CHIPS = (
    ("Bank rejected the debit", "Bank rejected the payment"),
    ("Autopay did not send it", "Autopay didn't send it"),
    ("Money already left the bank", "Money left my bank, but not showing in SIP"),
    ("Bank change", "Bank change"),
)
STEPPER = {
    "pay": ("Status", "Pay this month", "Received"),
    "renew": ("Autopay", "Confirm", "On"),
    "status": ("Status", "Wait", "Update"),
    "bank": ("Bank", "Update", "Saved"),
}


def apply_css():
    st.markdown(
        """
        <style>
          .stApp { background: #070b14; color: #e7edf5; }
          .block-container { padding-top: 1.1rem; max-width: 1180px; }
          [data-testid="stHeader"] { background: transparent; }
          h1, h2, h3, p, span, label, li { color: #e7edf5; }
          .dash-head {
            display: flex; justify-content: space-between; align-items: center;
            gap: 16px; margin: 0 0 16px;
          }
          .brand { font-size: 28px; font-weight: 750; letter-spacing: -0.03em; margin: 0; }
          .sub { color: #8ea0b8; font-size: 14px; margin: 4px 0 0; }
          .badge {
            border: 1px solid #3d5270; background: #152033; color: #c5d4e8;
            border-radius: 999px; padding: 8px 14px; font-size: 16px; font-weight: 700;
            white-space: nowrap;
          }
          [data-testid="stHorizontalBlock"] { align-items: flex-start; }
          .st-key-canvas, .st-key-sip_panel {
            background: #101826;
            border: 1px solid #243044;
            border-radius: 18px;
            padding: 16px 16px 8px;
          }
          .st-key-sip_help_history {
            min-height: 420px; max-height: 420px; overflow-y: auto; padding-right: 6px;
          }
          .st-key-sip_help_history p, .st-key-sip_help_archive p {
            white-space: normal; overflow: visible; font-size: 16px; line-height: 1.45;
          }
          .st-key-sip_help_archive { max-height: none; overflow: visible; }
          .st-key-sip_help_lower { margin-top: auto; }
          .card-title { font-size: 26px; font-weight: 750; margin: 0 0 8px; line-height: 1.3; }
          .summary { font-size: 16px; color: #d5deea; margin: 0 0 14px; }
          .summary b { color: #f4f7fb; }
          .section-label {
            color: #8ea0b8; font-size: 16px; font-weight: 650; margin: 8px 0;
          }
          .stepper { display: flex; align-items: center; gap: 8px; margin: 4px 0 10px; }
          .dot {
            width: 28px; height: 28px; border-radius: 999px; display: inline-flex;
            align-items: center; justify-content: center; font-size: 14px; font-weight: 700;
            border: 2px solid #3d5270; color: #9eb0c6; background: transparent;
          }
          .dot.on { border-color: #4c8dff; color: #d6e6ff; background: #15294a; }
          .dot.done { border-color: #4c8dff; color: #d6e6ff; }
          .step-label { color: #c5d4e8; font-size: 16px; }
          ol.guide { margin: 0 0 12px; padding-left: 1.2rem; }
          ol.guide li { font-size: 16px; line-height: 1.45; margin: 0 0 4px; }
          .jargon { color: #8ea0b8; font-size: 16px; margin: 0 0 10px; }
          .demo { color: #8ea0b8; font-size: 16px; margin: 8px 0 0; }
          .success {
            background: #152033; border: 1px solid #3d5270; border-radius: 14px;
            padding: 14px; margin-top: 8px;
          }
          .success p { font-size: 16px; margin: 0; color: #e7edf5; }
          .st-key-picked button {
            border: 2px solid #4c8dff !important;
            background: #101826 !important;
            color: #e7edf5 !important;
          }
          .st-key-go_wrap button {
            background: #00b386 !important;
            color: #04261c !important;
            border: none !important;
          }
          .st-key-back_wrap button, .st-key-again_wrap button {
            background: transparent !important;
            border: none !important;
            color: #9ecbff !important;
            text-decoration: underline;
            box-shadow: none !important;
          }
          .st-key-sip_panel [data-testid="stFormSubmitButton"] button,
          .st-key-screen_yes_wrap button {
            background: #8eb4ff !important;
            color: #0b1b33 !important;
            border: none !important;
          }
          .stTextInput input::placeholder { color: #b7c4d6 !important; opacity: 1; }
          div[data-testid="stButton"] button {
            min-height: 44px !important; height: auto !important;
          }
          div[data-testid="stButton"] button p {
            font-size: 16px !important; white-space: normal !important; line-height: 1.3 !important;
          }
          .st-key-chat_tools div[data-testid="stButton"] button {
            min-height: 32px !important;
            height: 32px !important;
            padding: 0 8px !important;
          }
          .st-key-chat_tools div[data-testid="stButton"] button p {
            font-size: 13px !important;
            font-weight: 600 !important;
          }
          .pill {
            display: inline-block; font-size: 13px; font-weight: 700;
            padding: 4px 10px; border-radius: 999px; margin: 0 0 10px;
          }
          .pill.warn { color: #f0c36a; background: #3a2e12; border: 1px solid #a67c2d; }
          .pill.wait { color: #9ecbff; background: #12283d; border: 1px solid #2d6ea3; }
          .pill.ok { color: #8ee0a8; background: #123024; border: 1px solid #2f8a5b; }
          .lead { font-size: 16px; line-height: 1.45; color: #f4f7fb; margin: 0 0 8px; }
          .next { font-size: 14px; line-height: 1.45; color: #b7c4d6; margin: 0 0 8px; }
          .steps { font-size: 12px; color: #8ea0b8; margin: 0 0 12px; }
          .steps b { color: #f4f7fb; }
          .warn-banner {
            background: #3a3414; border: 1px solid #8a7420; color: #f3e2a0;
            border-radius: 12px; padding: 10px 12px; margin: 0 0 12px; font-size: 14px;
          }
          .panel-title { font-size: 22px; font-weight: 750; margin: 0; }
          .panel-sub { color: #8ea0b8; font-size: 14px; margin: 4px 0 10px; }
          div[data-testid="stButton"] button {
            border-radius: 12px; background: #182233; color: #e7edf5; border: 1px solid #314158;
          }
          [data-testid="stChatMessage"] { background: #0c1422; border-radius: 14px; }
          [data-testid="stChatMessage"] p, [data-testid="stCaptionContainer"] { color: #d5deea; }
          .stTextInput input, .stTextArea textarea {
            background: #0c1422 !important; color: #e7edf5 !important;
            border: 1px solid #314158 !important; border-radius: 12px !important;
          }
          .foot { margin-top: 16px; color: #8ea0b8; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def guide_steps(item):
    data = facts()
    when = data["next_date"]
    amount = data["amount"]
    if item["kind"] == "renew":
        return [
            "UPI autopay lets the bank send it.",
            "It is off, so this debit can't go.",
            "Turn it on for the " + when + " debit.",
        ]
    if item["kind"] == "status":
        return [
            "The money already left your bank.",
            "Units can take a few days to show.",
            "There is no second payment.",
        ]
    if item["kind"] == "bank":
        return [
            "Add the account holder name if you want.",
            "Bank, account, phone, and address stay filled.",
            "They are filled as *** on this demo.",
        ]
    return [
        "The payment didn't go through.",
        "Pay only this " + amount + " instalment.",
        "The next date stays " + when + ".",
    ]


def stepper_html(kind, step):
    labels = STEPPER.get(kind) or STEPPER["pay"]
    index = {"home": 0, "confirm": 1, "done": 2}.get(step, 0)
    dots = []
    for number, _label in enumerate(labels, start=1):
        if number - 1 < index:
            mark = "✓"
            klass = "dot done"
        elif number - 1 == index:
            mark = str(number)
            klass = "dot on"
        else:
            mark = str(number)
            klass = "dot"
        dots.append(f"<span class='{klass}'>{mark}</span>")
    text = "Step " + str(index + 1) + " of 3 · " + labels[index]
    return (
        "<div class='stepper' aria-label='" + html.escape(text) + "'>"
        + "".join(dots)
        + "<span class='step-label'>" + html.escape(text) + "</span></div>"
    )


def success_html(item):
    data = facts()
    if item["kind"] == "renew":
        line = (
            "Autopay is on. Your next instalment of "
            + data["amount"]
            + " can go on "
            + data["next_date"]
            + "."
        )
    elif item["kind"] == "bank":
        line = (
            "The bank is updated with these masked details. Your next instalment of "
            + data["amount"]
            + " can go on "
            + data["next_date"]
            + "."
        )
    else:
        line = (
            "This month is marked received. Your next instalment of "
            + data["amount"]
            + " can go on "
            + data["next_date"]
            + "."
        )
    return (
        "<div class='success'><p>✓ "
        + html.escape(line)
        + "</p></div>"
    )


def set_step(step):
    st.session_state.step = step


def choose_situation(label):
    st.session_state.situation = label
    st.session_state.step = "home"
    st.session_state.filled_by_chat = False


def start_over():
    st.session_state.situation = ""
    st.session_state.step = "home"
    st.session_state.filled_by_chat = False
    st.session_state.screen_offer = None
    st.session_state.bank_holder_name = ""


def _bank_short(bank):
    import re
    found = re.search(r"(\d{4})", bank or "")
    if found:
        return "bank ending " + found.group(1)
    return bank


def render_bank_fields(include_send):
    """Account holder name is optional. The other bank details stay masked."""
    st.markdown("<p class='section-label'>New bank details</p>", unsafe_allow_html=True)
    if include_send:
        st.text_input(
            "Name of account holder",
            key="bank_holder_name",
            placeholder="Optional",
        )
    else:
        from chat.safety import mask

        typed = (st.session_state.get("bank_holder_name") or "").strip()
        shown, _changed = mask(typed)
        st.text_input(
            "Name of account holder",
            value=shown or "Not added",
            disabled=True,
        )
    for label in ("Bank name", "Account number", "Phone number", "Address"):
        st.text_input(label, value="***", disabled=True)
    if include_send:
        with st.container(key="go_wrap"):
            st.button("Send", type="primary", key="bank_send", on_click=set_step, args=("done",))


def render_canvas(item, step):
    data = facts()
    current = st.session_state.get("situation") or ""
    show_pick = bool(item) and step != "done"
    with st.container(key="canvas"):
        st.markdown(
            "<p class='card-title'>Your SIP instalment needs a quick fix</p>"
            "<p class='summary'><b>" + html.escape(data["amount"]) + "</b> due on the 5th · "
            + html.escape(_bank_short(data["bank"])) + "</p>"
            "<p class='section-label'>What happened?</p>",
            unsafe_allow_html=True,
        )
        for start in (0, 2):
            cols = st.columns(2)
            for offset, (label, display) in enumerate(CHIPS[start : start + 2]):
                selected = show_pick and label == current
                with cols[offset]:
                    with st.container(key="picked" if selected else "chip" + str(start + offset)):
                        st.button(
                            ("✓  " if selected else "") + display,
                            key="sit" + str(start + offset),
                            on_click=choose_situation,
                            args=(label,),
                        )
        if item and step == "done":
            st.markdown(success_html(item), unsafe_allow_html=True)
            if item["kind"] == "bank":
                render_bank_fields(False)
            with st.container(key="again_wrap"):
                st.button("Start over", key="again", on_click=start_over)
        elif item:
            steps = guide_steps(item)
            items = "".join("<li>" + html.escape(line) + "</li>" for line in steps)
            jargon = ""
            if item["kind"] == "renew":
                jargon = (
                    "<p class='jargon'>UPI autopay is your permission for the bank "
                    "to send the instalment each month.</p>"
                )
            elif item["kind"] == "bank":
                jargon = (
                    "<p class='jargon'>Only the account holder name can be typed, and it is optional. "
                    "The other details stay masked.</p>"
                )
            st.markdown(
                "<p class='section-label'>Here's what to do</p>"
                + stepper_html(item["kind"], step)
                + "<ol class='guide'>" + items + "</ol>"
                + jargon,
                unsafe_allow_html=True,
            )
            if item["kind"] != "status":
                if item["kind"] == "renew":
                    action = "Turn on autopay"
                else:
                    action = "Pay this instalment"
                if item["kind"] == "bank":
                    render_bank_fields(True)
                else:
                    with st.container(key="go_wrap"):
                        st.button(action, type="primary", key="go", on_click=set_step, args=("done",))
            if step == "confirm":
                with st.container(key="back_wrap"):
                    st.button("Back", key="back", on_click=set_step, args=("home",))
            st.markdown("<p class='demo'>Demo: no real payment is sent.</p>", unsafe_allow_html=True)


def main():
    st.set_page_config(
        page_title="Groww SIP help",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_css()
    if "step" not in st.session_state:
        st.session_state.step = "home"
    if "situation" not in st.session_state:
        st.session_state.situation = ""
    if st.session_state.get("keep_chat"):
        st.session_state.chat_open = True
        st.session_state.keep_chat = False
    apply_agent_screen()
    st.session_state.pop("agent_set_step", False)

    st.markdown(
        """
        <div class="dash-head">
          <div>
            <p class="brand">Groww SIP help</p>
            <p class="sub">This month's instalment. Confirming does not move money.</p>
          </div>
          <div class="badge">Not investment advice</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    label = st.session_state.situation or ""
    item = situation_by_label(label) if label else None
    canvas, chat = st.columns([1.05, 0.95], gap="medium", vertical_alignment="top")
    with canvas:
        render_canvas(item, st.session_state.step)

    st.session_state.scenario = label
    if item and item["kind"] == "renew" and st.session_state.step == "done":
        st.session_state.autopay_state = "on"
    elif item and item["kind"] == "renew":
        st.session_state.autopay_state = "off"
    else:
        st.session_state.autopay_state = ""

    from chat.ui import mount

    with chat:
        mount()

    st.markdown(
        "<p class='foot'>Helps with payment problems only. Not investment advice. "
        "Demo: no real payment, no real support agent.</p>",
        unsafe_allow_html=True,
    )


main()
