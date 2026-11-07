"""One Streamlit app with the discovery dashboard and the SIP help prototype.

Analysis of public comments. Not investment advice.
"""

import streamlit as st

import app as discovery
import mvp

st.set_page_config(
    page_title="Groww SIP continuation",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    "**Groww SIP continuation.** Public comments and a prototype. Not investment advice."
)
engine, prototype = st.tabs(["Discovery engine", "mvp - SIP help"])
with engine:
    discovery.main(embedded=True)
with prototype:
    mvp.main(embedded=True)
