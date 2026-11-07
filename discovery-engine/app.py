"""SIP continuation discovery dashboard.

Analysis of public comments. Not investment advice.
"""

import html
import importlib.util

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config

BLUE = "#0072B2"
ORANGE = "#E69F00"
INK = "#1F2933"


def load_py(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, config.ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@st.cache_resource
def scoring():
    return load_py("4_score.py", "score_mod")


@st.cache_resource
def tagger():
    return load_py("3_filter_tag.py", "tag_mod")


def file_mtime(path):
    if not path.exists():
        return 0
    return path.stat().st_mtime


@st.cache_data
def load_table(path_str, mtime):
    frame = config.read_csv(path_str)
    return frame


def footer():
    st.caption(config.NOT_ADVICE)


def banner():
    st.markdown(
        f"<div style='border:1px solid {BLUE}; padding:10px 14px; border-radius:8px;'>"
        f"{config.NOT_ADVICE}</div>",
        unsafe_allow_html=True,
    )


def final_frame():
    """Only comments retagged into final_retag.csv. The older final.csv tags are not shown."""
    path = config.DATA_DIR / "final_retag.csv"
    return load_table(str(path), file_mtime(path))


def retag_note(df):
    n = 0 if df is None or df.empty else len(df)
    if df is None or df.empty or "app" not in df.columns:
        covered = "none yet"
    else:
        labels = df["app"].fillna("").astype(str).str.strip().replace("", "YouTube, app not named")
        covered = ", ".join(f"{name} {int(count)}" for name, count in labels.value_counts().items())
    return (
        f"Showing {n} retagged comments only. Older tags are not included. "
        f"Apps covered: {covered}."
    )


APP_CHOICES = ["Groww", "Other apps", "YouTube with no app named", "All"]
TOO_FEW = "Too few comments to rely on"


def filter_app(df, choice):
    if df is None or df.empty or "app" not in df.columns or choice == "All":
        return df
    apps = df["app"].fillna("").astype(str).str.strip()
    if choice == "Groww":
        return df[apps.eq("Groww")].copy()
    if choice == "Other apps":
        return df[apps.ne("") & apps.ne("Groww")].copy()
    if choice == "YouTube with no app named":
        return df[apps.eq("")].copy()
    return df


def app_picker(tab_name):
    return st.selectbox("App", APP_CHOICES, index=0, key="app_" + tab_name)


def masked_quote(text):
    masked, _changed = scoring().mask_fund_names(text)
    return masked


def answers_frame():
    """Questions use the retagged file only, so old cache tags are not mixed in."""
    return final_frame()


def largest_leak(ok):
    if ok.empty:
        return None
    leaks = ok[ok["leak_type"].isin(["voluntary", "involuntary"])]
    pool = leaks if len(leaks) else ok[ok["tree_node"] != "none"]
    if pool.empty:
        return None
    return pool["tree_node"].value_counts().idxmax()


def overview_tab():
    funnel = config.load_funnel()
    st.subheader("From raw comments to the working set")
    st.write(
        "Top metric: share of first-time mutual fund investors who still have an active SIP "
        "12 months after starting. Active means at least one successful instalment in the last 30 days."
    )
    st.info(config.VOCAL_NOTE)
    if funnel:
        order = [
            ("raw_total", "Raw"),
            ("after_hygiene", "After hygiene"),
            ("after_keyword_cap", "After keyword gate"),
            ("after_relevance", "After relevance"),
            ("final_ok", "Tagged, confident"),
        ]
        labels = []
        values = []
        for key, label in order:
            if key in funnel:
                labels.append(label)
                values.append(int(funnel[key]))
        if labels:
            fig = go.Figure(go.Bar(x=labels, y=values, marker_color=BLUE, text=values, textposition="outside"))
            fig.update_layout(margin=dict(t=20, b=20), yaxis_title="Comments", height=360)
            st.plotly_chart(fig, use_container_width=True)
        if funnel.get("raw_by_source"):
            st.write("Raw comments by source")
            source = funnel["raw_by_source"]
            fig = go.Figure(
                go.Bar(x=list(source.keys()), y=list(source.values()), marker_color=BLUE, text=list(source.values()), textposition="outside")
            )
            fig.update_layout(margin=dict(t=20, b=20), height=320)
            st.plotly_chart(fig, use_container_width=True)
        if funnel.get("model"):
            st.caption("Model used for tagging: " + str(funnel["model"]))
    else:
        st.write("No funnel yet. Run the collect, clean, and tag scripts.")
    df = final_frame()
    if not df.empty:
        st.write("Working set by source")
        counts = df["source"].value_counts()
        fig = go.Figure(go.Bar(x=counts.index.tolist(), y=counts.values.tolist(), marker_color=ORANGE))
        fig.update_layout(margin=dict(t=20, b=20), height=320)
        st.plotly_chart(fig, use_container_width=True)
    footer()


def without_c2_non_instalment(frame):
    """Leave C2 comments that are not a recurring instalment out of the in-scope count."""
    if frame is None or frame.empty or "is_sip_instalment_issue" not in frame.columns:
        return frame
    drop = frame["tree_node"].astype(str).eq("C2") & frame["is_sip_instalment_issue"].astype(str).eq("no")
    return frame.loc[~drop].copy()


def instalment_note(frame):
    if frame is None or frame.empty or "is_sip_instalment_issue" not in frame.columns:
        return ""
    c2 = frame[frame["tree_node"].astype(str).eq("C2")]
    if c2.empty:
        return ""
    yes = int(c2["is_sip_instalment_issue"].astype(str).eq("yes").sum())
    return f"{yes} of {len(c2)} are clearly about a recurring SIP instalment"


def instalment_split(frame):
    if frame is None or frame.empty or "is_sip_instalment_issue" not in frame.columns:
        return pd.DataFrame()
    rows = []
    for node in config.SIP_INSTALMENT_NODES:
        part = frame[frame["tree_node"].astype(str).eq(node)]
        if part.empty:
            continue
        values = part["is_sip_instalment_issue"].astype(str)
        rows.append(
            {
                "tree_node": node,
                "yes": int(values.eq("yes").sum()),
                "no": int(values.eq("no").sum()),
                "unclear": int(values.eq("unclear").sum()),
                "comments": int(len(part)),
            }
        )
    return pd.DataFrame(rows)


def tree_tab(df, note=""):
    st.subheader("12-month active SIP")
    choice = app_picker("tree")
    shown = filter_app(df, choice)
    ok = scoring().usable(shown) if shown is not None and not shown.empty else shown
    has_issue = (
        ok is not None
        and not ok.empty
        and "is_sip_instalment_issue" in ok.columns
        and ok["is_sip_instalment_issue"].astype(str).str.strip().ne("").any()
    )
    tree_base = ok
    if has_issue and ok is not None and "metric_scope" in ok.columns:
        tree_base = ok[ok["metric_scope"].astype(str).eq("in_scope")].copy()
    tree_note = instalment_note(tree_base) if has_issue else note
    tree_shown = without_c2_non_instalment(tree_base) if has_issue else tree_base
    leak_node = largest_leak(tree_shown) if tree_shown is not None and not tree_shown.empty else None
    if tree_shown is None or tree_shown.empty:
        st.write("No confident tags yet.")
        footer()
        return
    if tree_note:
        st.caption("In-scope comments. C2 leaves out comments that are not a failed recurring instalment. Those comments stay in the file.")
    ok = tree_shown
    note = tree_note
    split_frame = tree_base if has_issue else None
    counts = ok["tree_node"].value_counts().to_dict()
    stages = [
        ("A. Start well", ["A1", "A2"]),
        ("B. Settle in, months 1–3", ["B1", "B2"]),
        ("C. Stay through the middle, months 4–9", ["C1", "C2", "C3"]),
        ("D. Reach month 12", ["D1"]),
        ("E. Recovery", ["E1"]),
    ]
    for title, nodes in stages:
        st.markdown(f"**{title}**")
        columns = st.columns(len(nodes))
        for column, node in zip(columns, nodes):
            n = int(counts.get(node, 0))
            biggest = node == leak_node
            border = "4px solid #111111" if biggest else f"1px solid {BLUE}"
            fill = ORANGE if biggest else "#E8F1F8"
            badge = "<div style='font-weight:700;margin-top:6px;'>Largest leak</div>" if biggest else ""
            extra = f"<div style='font-size:13px;margin-top:8px;'>{html.escape(note)}</div>" if node == "C2" and note else ""
            column.markdown(
                f"<div style='border:{border}; background:{fill}; color:{INK}; padding:12px; border-radius:8px; min-height:130px;'>"
                f"<div style='font-weight:700;'>{node}</div>"
                f"<div style='font-size:14px; margin:6px 0;'>{config.TREE[node]}</div>"
                f"<div style='font-size:22px;'>{n}</div>"
                f"{badge}{extra}</div>",
                unsafe_allow_html=True,
            )
    st.write("")
    ordered = [node for node in config.TREE if node != "none"]
    values = [int(counts.get(node, 0)) for node in ordered]
    colors = [ORANGE if node == leak_node else BLUE for node in ordered]
    widths = [3 if node == leak_node else 0 for node in ordered]
    fig = go.Figure(
        go.Bar(
            y=ordered,
            x=values,
            orientation="h",
            marker_color=colors,
            marker_line_color="#111111",
            marker_line_width=widths,
            text=["Largest leak" if node == leak_node else str(value) for node, value in zip(ordered, values)],
            textposition="outside",
        )
    )
    fig.update_layout(margin=dict(t=20, b=20, r=80), height=420, xaxis_title="Confident comments")
    st.plotly_chart(fig, use_container_width=True)
    split = instalment_split(split_frame if split_frame is not None else pd.DataFrame())
    if note:
        st.write(note)
    if not split.empty:
        st.markdown("**Is this a recurring SIP instalment problem?**")
        st.caption(
            "Yes means a recurring SIP instalment, autopay, or mandate failed, was missed, or was not debited. "
            "A one-time payment, add-money failure, or login or KYC error is no."
        )
        st.dataframe(split, hide_index=True, use_container_width=True)
    footer()


def sensitivity_block(df):
    st.markdown("**Score versions**")
    st.caption("Top 5 nodes other than none. The same four formulas are shown for Groww and for every retagged row.")
    score = scoring()
    views = [
        ("Groww", filter_app(df, "Groww")),
        ("All", df),
    ]
    tops = {}
    for label, frame in views:
        table, leaders = score.top_versions(frame)
        tops[label] = leaders
        st.markdown(f"**{label}**")
        if table is None or table.empty:
            st.write("No scored nodes yet.")
            continue
        columns = [
            "Frequency x Severity x Fixability",
            "Frequency x Severity",
            "Frequency only",
            "Frequency x Fixability",
        ]
        lines = []
        for column in columns:
            ordered = table.sort_values([column, "n"], ascending=[False, False]).head(5)
            bits = [f"{row['tree_node']} {row[column]}" for _, row in ordered.iterrows()]
            lines.append({"version": column, "top 5": ", ".join(bits)})
        st.dataframe(pd.DataFrame(lines), hide_index=True, use_container_width=True)
    groww_top = tops.get("Groww") or {}
    all_top = tops.get("All") or {}
    versions = [
        "Frequency x Severity x Fixability",
        "Frequency x Severity",
        "Frequency only",
        "Frequency x Fixability",
    ]
    changes = []
    for version in versions:
        left = groww_top.get(version, "")
        right = all_top.get(version, "")
        if left and right and left != right:
            changes.append(f"{version}: Groww {left}, All {right}")
    groww_nodes = [groww_top.get(version, "") for version in versions if groww_top.get(version, "")]
    all_nodes = [all_top.get(version, "") for version in versions if all_top.get(version, "")]
    if groww_nodes and len(set(groww_nodes)) > 1:
        st.write("On Groww, the top node is not the same in every version.")
    else:
        st.write("On Groww, the top node is the same in every version.")
    if all_nodes and len(set(all_nodes)) > 1:
        st.write("On All, the top node is not the same in every version.")
    else:
        st.write("On All, the top node is the same in every version.")
    if changes:
        st.write("The top node differs between Groww and All: " + "; ".join(changes) + ".")
    else:
        st.write("The top node for Groww matches the top node for All in each version.")


def ranking_tab(df):
    st.subheader("Where comments concentrate")
    st.info(config.VOCAL_NOTE)
    choice = app_picker("ranking")
    df = filter_app(df, choice)
    if len(scoring().usable(df)) < 30:
        st.write(TOO_FEW)
    in_scope_only = True
    if "metric_scope" in df.columns:
        in_scope_only = st.toggle("In-scope only", value=True)
        st.caption(
            "In-scope means the comment is about starting, keeping, pausing, failing, or restarting a SIP. "
            "Exit complaints stay in the file and in the section below."
        )
    work = df
    if in_scope_only and "metric_scope" in df.columns:
        work = df[df["metric_scope"].astype(str) == "in_scope"]
        work = without_c2_non_instalment(work)
    ranking = scoring().build_ranking(work) if work is not None and not work.empty else pd.DataFrame()
    leak_node = largest_leak(scoring().usable(work)) if work is not None and not work.empty else None
    if ranking.empty:
        st.write("No ranking yet.")
        footer()
        return
    overall = ranking[ranking["slice_type"] == "all"].copy()
    if overall.empty:
        st.write("No overall scores yet.")
    else:
        show = overall[
            [
                "tree_node",
                "node_label",
                "n",
                "frequency",
                "severity",
                "fixability",
                "score",
                "voluntary_n",
                "involuntary_n",
                "note",
                "fixability_reason",
            ]
        ]
        st.dataframe(show, use_container_width=True, hide_index=True)
        colors = [ORANGE if node == leak_node else BLUE for node in overall["tree_node"]]
        fig = go.Figure(
            go.Bar(
                x=overall["tree_node"],
                y=overall["score"],
                marker_color=colors,
                marker_line_color="#111111",
                marker_line_width=[3 if node == leak_node else 0 for node in overall["tree_node"]],
                text=["Largest leak" if node == leak_node else "" for node in overall["tree_node"]],
                textposition="outside",
            )
        )
        fig.update_layout(margin=dict(t=20, b=20), yaxis_title="Frequency × severity × fixability", height=360)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Fixability is set by hand in config.py. The model does not choose it.")
        st.caption(
            "Severity is 3 when the SIP stopped and did not restart, "
            "2 when it was paused, reduced, or the person is considering stopping, "
            "and 1 when they are confused or complaining but still continuing, "
            "including a failed debit that the comment does not say ended the SIP."
        )
        sensitivity_block(final_frame())
    if "metric_scope" in df.columns:
        exit_rows = df[df["metric_scope"].astype(str) == "exit_experience"]
        st.subheader("Exit experience (outside the 12-month metric)")
        st.write(
            f"{len(exit_rows)} comments are about leaving: redemption speed, withdrawal delay, "
            "account closure, or support after the person had already decided to go. "
            "They are kept. They are not the continuation lever."
        )
        if not exit_rows.empty:
            columns = [col for col in ["app", "tree_node", "action_taken", "text"] if col in exit_rows.columns]
            scroll_table(exit_rows[columns], {"text"})
    footer()


def themes_tab(df, ranking):
    st.subheader("What people are trying to do")
    score = scoring()
    if usable_empty(df):
        st.write("No confident tags yet.")
        footer()
        return
    left, right = st.columns(2)
    with left:
        st.markdown("**Confusion points**")
        st.dataframe(score.top_counts(df, "confusion_point"), hide_index=True, use_container_width=True)
        st.markdown("**Unmet needs, in the words that were tagged**")
        st.dataframe(score.top_counts(df, "unmet_need"), hide_index=True, use_container_width=True)
    with right:
        st.markdown("**Workarounds outside the app**")
        st.dataframe(score.top_counts(df, "workaround_outside_app"), hide_index=True, use_container_width=True)
        st.markdown("**Voluntary and involuntary by stage**")
        st.dataframe(score.stage_split(df), hide_index=True, use_container_width=True)

    st.markdown("**Short quotes**")
    for node, quotes in score.quotes_by_node(df).items():
        st.markdown(f"**{node}** — {config.TREE[node]}")
        for quote in quotes:
            st.markdown("> " + masked_quote(quote))

    st.markdown("**Groww, other apps, and YouTube**")
    mix = score.brand_mix(df)
    if mix.empty:
        st.write("No brand mix yet.")
    else:
        st.dataframe(mix, hide_index=True, use_container_width=True)
        small = mix[mix["note"] != ""]["brand"].unique().tolist()
        if small:
            st.caption("Small samples: " + ", ".join(small) + ". " + config.SMALL_SAMPLE_NOTE)

    st.markdown("**Segments**")
    show_unclear = st.checkbox("Show unclear segment values", value=False)
    if ranking.empty:
        st.write("No segment scores yet.")
    else:
        choice = st.selectbox("Cut", ["income_type", "age_hint", "influenced_by"])
        part = ranking[ranking["slice_type"] == choice].copy()
        if not show_unclear:
            part = part[part["slice_value"].astype(str).str.lower() != "unclear"]
        if part.empty:
            st.write("No rows for this cut.")
        else:
            st.dataframe(
                part[["slice_value", "tree_node", "n", "frequency", "severity", "fixability", "score", "note"]],
                hide_index=True,
                use_container_width=True,
            )
    footer()


def scroll_table(frame, tall_columns):
    """Show a table whose long text can be scrolled inside the cell."""
    shown = frame.head(300).fillna("")
    header = "".join(
        "<th style='text-align:left;padding:8px;border-bottom:1px solid #d0d7de;background:#f6f8fa;'>"
        + html.escape(str(column))
        + "</th>"
        for column in shown.columns
    )
    rows = []
    for _, row in shown.iterrows():
        cells = []
        for column in shown.columns:
            value = html.escape(str(row[column]))
            if column in tall_columns:
                cell = (
                    "<div style='max-height:120px;max-width:560px;overflow:auto;"
                    "white-space:pre-wrap;line-height:1.4;'>"
                    + value
                    + "</div>"
                )
            else:
                cell = value
            cells.append(
                "<td style='padding:8px;vertical-align:top;border-bottom:1px solid #eee;'>"
                + cell
                + "</td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    table = (
        "<div style='overflow:auto;max-height:680px;border:1px solid #d0d7de;border-radius:8px;'>"
        "<table style='border-collapse:collapse;width:100%;font-size:14px;'>"
        "<thead><tr>"
        + header
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )
    st.markdown(table, unsafe_allow_html=True)


def questions_tab(df):
    st.subheader("Ask the comments")
    choice = app_picker("questions")
    df = filter_app(df, choice)
    if len(scoring().usable(df)) < 30:
        st.write(TOO_FEW)
    st.write("Enter one question. The answer is counted from the tagged public comments.")
    st.caption(config.VOCAL_NOTE)
    question = st.text_input("Your question", placeholder="For example: why do people pause a SIP?")
    if st.button("Find the answer"):
        st.session_state["asked_question"] = question
    asked = st.session_state.get("asked_question", "")
    if not asked:
        footer()
        return
    block = scoring().answer_question(df, asked)
    st.markdown(f"**{block['question']}**")
    st.write(block["lead"])
    if block.get("note"):
        st.caption(block["note"])
    for title, table in block.get("tables") or []:
        if table is None or getattr(table, "empty", True):
            continue
        if title:
            st.markdown(title)
        if "evidence_quote" in table.columns:
            table = table.copy()
            table["evidence_quote"] = table["evidence_quote"].map(masked_quote)
        if "example" in table.columns:
            table = table.copy()
            table["example"] = table["example"].map(masked_quote)
        tall = [column for column in ("example", "text", "evidence_quote") if column in table.columns]
        if tall:
            scroll_table(table, tall)
        else:
            st.dataframe(table, hide_index=True, use_container_width=True)
    for quote in block.get("quotes") or []:
        st.markdown("> " + masked_quote(quote))
    footer()


def usable_empty(df):
    return scoring().usable(df).empty


def try_tab():
    st.subheader("Tag one comment")
    st.write("Paste a public comment. If the model is unsure, it will say so instead of assigning a tag.")
    text = st.text_area("Comment", height=140)
    if st.button("Tag this comment"):
        if not str(text).strip():
            st.write("Paste a comment first.")
        elif not any((config.HF_TOKEN, config.GROQ_API_KEY, config.GEMINI_API_KEY, config.NVIDIA_API_KEY)):
            st.write("Not sure, needs human review")
            st.caption("No model key is loaded.")
        else:
            with st.spinner("Reading the comment"):
                try:
                    tag = tagger().tag_one(text)
                except Exception:
                    tag = {"status": "needs_review", "confidence": 0, "evidence_quote": "", "notice": "The model did not return a tag."}
            confidence = float(tag.get("confidence") or 0)
            unsure = tag.get("status") != "ok" or confidence < config.CONFIDENCE_MIN
            if unsure:
                st.warning("Not sure, needs human review")
                if tag.get("notice"):
                    st.caption(tag["notice"])
            else:
                st.markdown(f"**{tag.get('tree_node')}** — {config.TREE.get(tag.get('tree_node'), '')}")
                st.write(
                    {
                        "journey_stage": tag.get("journey_stage"),
                        "leak_type": tag.get("leak_type"),
                        "action_taken": tag.get("action_taken"),
                        "trigger": tag.get("trigger"),
                        "confusion_point": tag.get("confusion_point"),
                        "unmet_need": tag.get("unmet_need"),
                        "emotion": tag.get("emotion"),
                    }
                )
            st.write(f"Confidence: {confidence:.2f}")
            if tag.get("evidence_quote"):
                st.markdown("> " + masked_quote(tag.get("evidence_quote")))
    footer()


def review_tab():
    st.subheader("Needs a person")
    df = final_frame()
    if not df.empty and "status" in df.columns:
        queue = df[df["status"].astype(str).str.lower() == "needs_review"]
    else:
        queue = df
    if queue.empty:
        st.write("No rows are waiting.")
        footer()
        return
    st.write(f"{len(queue)} comments are low confidence, failed a check, or the model did not answer.")
    st.caption("Scroll inside a comment to read the rest of it.")
    columns = [col for col in ["id", "source", "app", "text", "confidence", "tree_node", "metric_scope", "evidence_quote", "status"] if col in queue.columns]
    view = queue[columns].copy()
    if "evidence_quote" in view.columns:
        view["evidence_quote"] = view["evidence_quote"].map(masked_quote)
    scroll_table(view, {"text", "evidence_quote"})
    if len(queue) > 300:
        st.caption("Showing the first 300 retagged comments. The full list is in data/final_retag.csv.")
    footer()


def main():
    st.set_page_config(page_title="SIP continuation discovery", layout="wide")
    st.title("SIP continuation discovery")
    st.write("Public comments about starting, keeping, pausing, or failing a SIP, mapped onto one metric tree.")
    banner()
    df = final_frame()
    st.info(retag_note(df))
    ok = scoring().usable(df) if not df.empty else df
    tree_base = ok
    has_issue = (
        not ok.empty
        and "is_sip_instalment_issue" in ok.columns
        and ok["is_sip_instalment_issue"].astype(str).str.strip().ne("").any()
    )
    if has_issue and "metric_scope" in ok.columns:
        tree_base = ok[ok["metric_scope"].astype(str).eq("in_scope")].copy()
    note = instalment_note(tree_base) if has_issue else ""
    tree_shown = without_c2_non_instalment(tree_base) if has_issue else tree_base
    leak_node = largest_leak(tree_shown) if tree_shown is not None and not tree_shown.empty else None
    ranking = scoring().build_ranking(df) if not df.empty else pd.DataFrame()

    tabs = st.tabs(
        ["Overview", "Questions", "Metric tree", "Ranking", "Themes and segments", "Try it", "Needs review"]
    )
    with tabs[0]:
        overview_tab()
    with tabs[1]:
        questions_tab(answers_frame())
    with tabs[2]:
        tree_tab(df, note)
    with tabs[3]:
        ranking_tab(df)
    with tabs[4]:
        themes_tab(df, ranking)
    with tabs[5]:
        try_tab()
    with tabs[6]:
        review_tab()


if __name__ == "__main__":
    main()
