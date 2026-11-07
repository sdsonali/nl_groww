# Discovery Engine + Metric Breakdown: Build Plan (for Cursor)

> Paste this whole file into Cursor and say: **"Build this step by step. Finish one phase, show me it works, then stop and wait for me."**

---

## 0. Context

**Product:** Groww (Indian investing app). We are the Growth Team PM.
**Business goal:** Increase the % of first-time mutual fund investors who still have an **active SIP 12 months after starting**. "Active" = at least one successful instalment in the last 30 days. (SIP = Systematic Investment Plan: a fixed amount auto-invested every month.)
**What this tool does:** Collects public comments about SIPs, throws away garbage, keeps only **1,500 to 3,000 relevant comments**, tags each one against our metric tree, and ranks where users are lost.

### Hard rules (never break)
1. Never recommend specific funds or stocks, in code, prompts, or output.
2. Never use fear, FOMO, or urgency language in any output.
3. This tool analyses public text only. It is **not investment advice**. Show this line on every dashboard page.
4. Store **no usernames, profile links, or personal identifiers**. Strip them at collection time.
5. **No Reddit.** Do not build a Reddit scraper or API call.
6. **No model weights are downloaded. All AI runs through the Hugging Face free Inference API.** Do not install `torch`, `transformers`, `sentence-transformers`, or any package that downloads a model onto this machine.
7. Everything must be free to run.

### Simplicity principle
Plain Python scripts, CSV files, one Streamlit page. No frameworks, no classes unless needed, no database.

---

## 1. Setup (do this first, before any code)

Create a virtual environment and install every library inside it.

```bash
mkdir discovery-engine && cd discovery-engine
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install requests pandas python-dotenv google-play-scraper google-api-python-client huggingface_hub streamlit plotly
pip freeze > requirements.txt
```

Libraries and why:
| Library | Use |
|---|---|
| `requests` | Apple App Store review feed |
| `pandas` | Read, clean, and save CSV files |
| `python-dotenv` | Load keys from `.env` |
| `google-play-scraper` | Play Store reviews |
| `google-api-python-client` | YouTube Data API |
| `huggingface_hub` | Calls the Hugging Face API (no model download) |
| `streamlit` | Dashboard |
| `plotly` | Charts |

Create `.env` (the PM adds the real values; never commit this file, add it to `.gitignore`):
```
HF_TOKEN=
HF_MODEL=
YOUTUBE_API_KEY=
```
`HF_MODEL` is a setting, not hardcoded, so we can swap models in one line. Free-tier model availability and rate limits change, so test two or three instruct models of roughly 7-8B size before choosing.

---

## 2. Folder structure (flat and simple)

```
discovery-engine/
├── .env
├── .gitignore
├── requirements.txt
├── config.py            # keywords, app IDs, video list, tree nodes, fixability scores
├── 1_collect.py         # Play Store, App Store, YouTube -> data/raw.csv
├── 2_clean.py           # dedupe, remove PII, keyword gate -> data/clean.csv
├── 3_filter_tag.py      # AI relevance check + tagging -> data/final.csv
├── 4_score.py           # opportunity ranking -> data/ranking.csv
├── 5_evaluate.py        # golden set comparison -> printed report
├── app.py               # Streamlit dashboard
└── data/                # all CSV files live here
```

That is the whole project. No subfolders of code.

---

## 3. Data sources

| Source | Target raw volume | Notes |
|---|---|---|
| Play Store: Groww | up to 20,000 | Country `in`, languages `en` and `hi` |
| Play Store: competitors (Zerodha Coin, INDmoney, ET Money, Kuvera, Paytm Money) | up to 5,000 each | Keep `app` column so they stay a separate comparison set |
| App Store (public RSS JSON feed): same apps | up to about 500 each | Feed only returns recent reviews |
| YouTube comments | up to 20,000 | From 30-50 Indian personal-finance videos on SIP for beginners, "SIP stopped", "should I continue SIP". Also save video title and description |

Optional manual file: `data/manual_forums.csv` (columns `text, source_label, date`) where the PM can paste public forum excerpts by hand. Loaded if it exists. No scraping.

**Raw columns:** `id, source, app, text, rating, date, video_id, context` (context = app name or video title). **No username column.**

Use official APIs, add short delays between requests, and save raw data before any processing so we never re-collect.

---

## 4. The garbage filter (reaching 1,500-3,000)

All AI steps use the Hugging Face API. Log the row count after every step (this becomes the funnel in the Evidence Log).

**Step A: Hygiene (code only, in `2_clean.py`)**
- Remove duplicates and near-duplicates.
- Remove text under 5 words or 25 characters.
- Remove emoji-only text and spam ("DM me", "telegram", "join my group").
- Remove phone numbers, emails, @handles, links.
- Keep Hinglish. Do not drop it.

**Step B: Keyword gate (code only, in `2_clean.py`)**
Keep rows with at least one SIP-related term from `config.py`, for example: `sip, mutual fund, instalment, installment, autopay, auto debit, mandate, nach, nav, folio, paused, stopped, cancel, skipped, bounce, failed, statement, xirr, step up, redeem, withdraw`, plus Hinglish such as `sip band, band kar, paisa kat, nahi kata`.
Count how many keywords each row matches and sort by that count. If more than 6,000 rows remain, keep only the top 6,000 by match count. This keeps API usage inside free limits.

**Step C: Batched AI relevance check (API, in `3_filter_tag.py`)**
Send **20 comments per API call**. The model returns, for each comment id, `relevant: true/false`. Question: "Is this person talking about starting, continuing, pausing, stopping, or failing at a SIP or mutual fund investing?" Drop the false rows. Batching cuts calls about 20 times.

**Step D: AI tagging (API, in `3_filter_tag.py`)**
Tag each survivor with the schema in section 5, **5 comments per call** or one per call if the model struggles with batches. Cache every response in `data/cache.json` by row id so reruns are free. Add retry with waiting when the API rate-limits.

**Final trim**
- Target **1,500 to 3,000** rows. Hard cap 3,000.
- Rank by confidence, then keyword match count, and keep the top 3,000.
- If fewer than 1,500 survive, loosen Step B slightly; do not lower the bar so far that samples look noisy.
- Aim for at least 40% from Groww itself; no single source above 60%.
- Save as `data/final.csv`. Remove the rest from the working set.

---

## 5. Metric breakdown (Part 2) and tagging schema

**Top metric:** 12-month SIP continuation % for first-time investors.

```
12-month active SIP %
├── A. START WELL
│   A1. SIP set up and first instalment debited successfully
│   A2. Setup completed without abandoning
├── B. SETTLE IN (months 1-3)
│   B1. 2nd and 3rd instalments succeed
│   B2. Investor does not cancel after first statement / first look at value
├── C. STAY THROUGH THE MIDDLE (months 4-9)
│   C1. Voluntary leaks: pause, cancel, reduce, redeem-and-leave
│   C2. Involuntary leaks: failed debit, expired mandate, bank change, low balance
│   C3. Failed-debit recovery: user notices and fixes it in time
├── D. REACH MONTH 12
│   D1. Instalment successful in last 30 days
└── E. RECOVERY LOOP
    E1. Paused or failed users who restart
```
Every leak is **voluntary** (user chose) or **involuntary** (it failed, user may not know). They need different fixes.

**Tag every relevant comment with this JSON (validate it in code):**
```json
{
  "is_relevant": true,
  "journey_stage": "start | settle_in_m1_3 | middle_m4_9 | month_12_plus | restart | unclear",
  "tree_node": "A1 | A2 | B1 | B2 | C1 | C2 | C3 | D1 | E1 | none",
  "leak_type": "voluntary | involuntary | none | unclear",
  "action_taken": "paused | cancelled | reduced | continued | failed_debit | restarted | considering | none",
  "trigger": "short phrase: what happened just before",
  "confusion_point": "short phrase or null",
  "what_they_check": "app_value | nav | statement | returns_calculator | news | none | unclear",
  "workaround_outside_app": "google | youtube | friends_family | advisor | calculator | other | none",
  "income_type": "salaried | irregular | student | unclear",
  "age_hint": "under_25 | 25_35 | 35_plus | unclear",
  "influenced_by": "friend | youtuber | app_nudge | family | self | unclear",
  "emotion": "confused | anxious | disappointed | neutral | satisfied | angry",
  "unmet_need": "one line in the user's own words",
  "evidence_quote": "exact short phrase copied from the text, max 15 words",
  "confidence": 0.0
}
```

**Prompt rules:**
- Use only the text given. If unsure, say `unclear` with low confidence. Never guess.
- `evidence_quote` must be an exact substring of the comment. Code checks this. If it fails, mark the row `needs_review`.
- Never mention or suggest any fund or stock.
- Handle Hinglish and sarcasm. Separate "NAV went down" (market) from "my SIP failed" (system).
- Include 5-6 short examples in the prompt (Hinglish, a failed debit, a voluntary pause, an irrelevant comment).
- Return JSON only. If parsing fails, retry once, then mark `needs_review`.

**Safe fallback:** confidence under 0.6, failed validation, or an API error means `needs_review`. These rows are left out of rankings until a human checks them. Never invent a tag.

---

## 6. Opportunity scoring (`4_score.py`)

For each tree node, and for each segment cut (income type, age hint, influenced_by):

```
Opportunity score = Frequency x Severity x Fixability
```
- **Frequency:** share of relevant comments tagged to that node.
- **Severity (1-3):** 3 = cancelled/failed/stopped, 2 = paused/reduced, 1 = confused or considering (computed from `action_taken`).
- **Fixability (1-3):** how fixable in-app **without advice, fund picks, or fear/FOMO**. **Set by the PM by hand in `config.py`, with a one-line reason.** The AI must not decide this.

Also output: voluntary vs involuntary split per stage, top confusion points, top unmet needs, top workarounds, Groww vs competitors, and 3 short quotes (under 15 words) per theme. Show a note for any group with fewer than 30 rows.

On the dashboard, show: **"Comments show what vocal users say, not true population rates. Quiet drop-offs are covered in interviews."**

---

## 7. Human-in-the-loop (where the PM must step in)

| # | Where | What the human does | Why |
|---|---|---|---|
| 1 | Before Step B | Read 50 raw rows, extend the keyword list | Our keywords may miss how real users talk |
| 2 | After Step B and C | Spot-check **30 discarded rows** to see if good comments were thrown away | Catches false removals, which silent filters hide |
| 3 | Before AI tagging results are used | **Hand-label the 20-25 item golden set first, without looking at AI tags** | Fair test of AI accuracy |
| 4 | After tagging | Review the `needs_review` queue (low-confidence rows) | AI says "not sure", a human decides |
| 5 | Scoring | Set Fixability scores and reasons by hand | This is PM judgement, not AI judgement |
| 6 | Correction log | Record 2-3 places you corrected the AI and why | Required for the Evidence Log |
| 7 | Before the deck | Read the top quotes and themes, and reject any that do not match the raw text | AI summaries can sound right and be wrong |

The AI proposes. The human decides on anything that feeds a conclusion in the deck.

---

## 8. Quality check and Evidence Log support (`5_evaluate.py`)

- A helper picks **20-25 random rows** from `final.csv`, spread across sources and stages, and writes them to `data/golden.csv` with empty label columns for the PM to fill.
- After the PM labels them, `5_evaluate.py` prints:
  - Agreement % per field and overall (at least `is_relevant`, `tree_node`, `leak_type`, `action_taken`).
  - A table of every disagreement, AI label vs human label, so we can explain failures (sarcasm, Hinglish, market vs system).
- **Targets:** at least 85% agreement on `is_relevant` and 75% on `tree_node`. If lower, improve the prompt or switch `HF_MODEL`, and record each attempt.
- `data/corrections.csv` columns: `row_id, text, ai_output, human_correction, reason, prompt_change`.
- The script also prints the funnel counts (raw per source, after each step, final), the golden set results, and a privacy line: public data only, no usernames stored.

---

## 9. Dashboard (`app.py`, the public link)

Streamlit, one file, simple tabs. Footer on every tab: **"Analysis of public comments. Not investment advice."**

1. **Overview:** funnel from raw to final, source mix.
2. **Metric tree:** counts per node. Highlight the biggest leak with a **thick outline plus a text label**, not colour alone. Use a colour-blind-safe palette (blue and orange).
3. **Ranking:** table with Frequency, Severity, Fixability, Score.
4. **Themes and segments:** confusion points, workarounds, unmet needs, segment comparison.
5. **Try it:** paste a comment, see the AI tag, confidence, and evidence quote. If confidence is low, show "Not sure, needs human review" instead of a tag.
6. **Needs review:** the low-confidence rows.

Deploy on Hugging Face Spaces or Streamlit Community Cloud for a public link. API keys go in the platform's secrets settings, never in the repo.

---

## 10. Build order (one phase at a time, stop after each)

| Phase | Task | Done when |
|---|---|---|
| 0 | Create `.venv`, install libraries, create `.env`, `.gitignore`, `config.py` | `pip list` shows libraries; no model-weight packages installed |
| 1 | `1_collect.py` for Play Store and App Store | `data/raw.csv` has rows, no username column |
| 2 | Add YouTube to `1_collect.py` | YouTube rows appear with video context |
| 3 | `2_clean.py` (Steps A and B) | Row counts printed per step |
| 4 | `3_filter_tag.py` Step C (batched relevance) | A 200-row test batch runs; PM spot-checks discards |
| 5 | Step D tagging with cache, retries, validation, fallback | A 50-row test batch tags correctly |
| 6 | Full run and trim to 1,500-3,000 | `data/final.csv` exists |
| 7 | `4_score.py` | `data/ranking.csv` printed |
| 8 | `5_evaluate.py` and golden set | Agreement report works |
| 9 | `app.py` and deploy | Public link works |

After each phase: print row counts, show 5 sample rows, and wait for the PM.

---

## 11. Compliance checklist

- **Privacy (DPDP Act):** public text only, no usernames or profile data stored, personal details removed. Add a short data note to the README. If a platform's data-use terms are unclear, say so in the README. Do not assume.
- **SEBI:** no advice, no fund or stock names, no return predictions. Add an output filter: if any model output names a fund or stock, replace it with "Not available" and log it.
- **Fairness:** compare segments carefully and flag small samples.
- **Honest limits:** comments over-represent angry and happy users.
- **Safe fallback:** low confidence, parse failure, or API error leads to "Not sure" and human review.

---

## 12. Definition of done

- 1,500 to 3,000 relevant, tagged, validated rows in `data/final.csv`.
- Funnel counts logged for every step.
- Ranked leak list mapped to the metric tree, with the voluntary vs involuntary split.
- Golden set with agreement report and failure list; 2-3 logged corrections.
- Public Streamlit link with the "Try it" box, needs-review tab, and not-advice footer.
- Virtual environment used throughout; no model weights downloaded; no Reddit code; no usernames stored; no fund or stock names in any output.
