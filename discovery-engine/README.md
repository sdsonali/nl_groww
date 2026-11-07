# SIP continuation discovery

This tool reads public comments about SIPs and sorts them onto one question:

**Of people who start a mutual-fund SIP, how many still have one running 12 months later?**

“Still running” means at least one successful instalment in the last 30 days. A SIP here means a fixed amount invested every month.

It is a reading aid for the growth team. It does not give investment advice, and it does not recommend a fund or a stock. Every dashboard tab ends with: **Analysis of public comments. Not investment advice.**

Comments show what vocal users say. They are not the true rate for every customer. Quiet drop-offs need interviews.

## What is already done

1. **Collect.** Public reviews were gathered and saved in `data/raw.csv` (54,553 comments after three later hand-pasted lines).
   - Play Store: 45,645 (Groww up to 20,000; Zerodha Coin, INDmoney, ET Money, Kuvera, and Paytm Money up to about 5,000 each).
   - YouTube: 5,905, from the official YouTube Data API.
   - App Store: 2,990, from Apple’s public review feed (about 500 per app).
   - Hand-pasted lines: 13, in `data/manual_forums.csv` (Trustpilot, Mouthshut, Pissed Consumer, Reddit text someone already read, Quora, LinkedIn, and two interview lines). Reddit was not scraped.
2. **Clean.** Short comments, duplicates, and comments that never mention a SIP were removed. **5,992** comments are in `data/clean.csv`. Another 112 sit in `data/loose.csv` as a spare list.
3. **Label.** The current tags come from NVIDIA’s free Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`), one comment per call, at temperature 0. Each call returns the tree box, metric scope, SIP outcome, whether it is a recurring instalment problem, a tenure hint, a confusion, an unmet need, a workaround, a short quote, and a confidence. The dashboard reads only `data/final_retag.csv`. Older tags stay in `data/final.csv` and `data/final_v1_old_prompt.csv` and are not mixed in. `data/cache.json` is the older run’s saved answers and is not overwritten by the retag.
4. **Dashboard.** A local Streamlit page with seven tabs. Questions, Metric tree, and Ranking each have an App dropdown (Groww, Other apps, YouTube with no app named, All). It opens on Groww. Open it at [http://localhost:8501](http://localhost:8501) after the command in [Open the dashboard](#open-the-dashboard).

Hugging Face was tried first. The account can sign in, but the free inference credit is used up, so those models return an error. Gemini’s free tier was tried next and was too slow because of daily quota. NVIDIA’s free prototyping API is the one the tagger uses now. No model weights are downloaded.

Fund and scheme names in quotes shown on the page are replaced with `[fund name]`. The CSV files keep the original text. The name list can miss a fund. That limit is stated here on purpose.

## Rules

- Store public comment text only. Usernames, profile links, channel names, emails, phone numbers, and @handles are stripped when comments are collected. Do not add them back.
- Do not scrape Reddit, and do not call the Reddit API. A person may paste a public excerpt they already read into `data/manual_forums.csv`.
- Do not install `torch`, `transformers`, or `sentence-transformers`. All model calls go through an API.
- Use free model keys only. Do not put a paid model in `.env`.
- Keys live only in `discovery-engine/.env`. That file is not committed.

Sources:

- **YouTube** uses the official YouTube Data API. Use must follow the YouTube API Services Terms of Service. A video title can be stored so a comment has context. The commenter’s name is not stored.
- **App Store** reviews come from Apple’s public RSS customer-review feed.
- **Play Store** reviews are read from the public listing through `google-play-scraper`. That library is not an official Google API. If that use is unclear against Google’s terms, stop using this source.
- **Forums** are pasted by hand.

If a platform’s terms are unclear, pause that source.

## Project structure

The plan this folder was built from is `../discovery_engine_plan.md` (one folder above `discovery-engine`).

```text
discovery-engine/
├── README.md            This guide
├── requirements.txt     Packages for the dashboard and the prototype
├── requirements-full.txt  Collection, tagging, and every pinned package
├── .gitignore           Files git should skip (.env, data, .venv)
├── .env                 Your secret keys. Never commit this.
├── .venv/               Local Python packages. Created by the setup commands.
├── config.py            Apps, keywords, metric tree, and key loading
├── 1_collect.py         Downloads public comments into data/raw.csv
├── 2_clean.py           Drops junk and keeps SIP comments in data/clean.csv
├── 3_filter_tag.py      Asks the model which comments matter, then labels them
├── 4_score.py           Ranks the labelled problems and writes data/ranking.csv
├── 5_evaluate.py        Builds a sample for a person to check
├── app.py               The dashboard
└── data/                All comment files and saved progress
```

### What each code file does

| File | What it does |
| --- | --- |
| `config.py` | The settings. Which apps to read, which words count as a SIP, the 12-month tree, how serious each leak is, and how to read `.env`. Change fixability scores here. The model does not set them. |
| `1_collect.py` | Reads Play Store, App Store, YouTube, and `data/manual_forums.csv`. Writes `data/raw.csv`, `data/videos.csv`, and the raw counts in `data/funnel.json`. |
| `2_clean.py` | Removes very short comments, spam, duplicates, and comments with no SIP words. Writes `data/clean.csv`, a spare `data/loose.csv`, and `data/discarded_keyword_sample.csv`. |
| `3_filter_tag.py` | Calls the model. The retag sends one comment per call and writes `data/final_retag.csv`. It does not write `data/cache.json`. |
| `4_score.py` | Counts the confident labels in `data/final_retag.csv` and ranks leaks. Writes `data/ranking.csv` and `data/problem_candidates.csv`. Also answers the typed questions on the dashboard. |
| `5_evaluate.py` | Writes `data/golden.csv` once, for a person to label by hand. Creates `data/corrections.csv` if it is missing. Does not overwrite a golden file that already exists. |
| `app.py` | The seven-tab dashboard. |

### What each data file contains

| File | What is inside |
| --- | --- |
| `data/manual_forums.csv` | The only data file you edit by hand. Columns: `text`, `source_label`, `date`. Dates are `YYYY-MM-DD`. Leave `date` empty when the page shows none. |
| `data/raw.csv` | Every collected comment after names and emails are stripped. Columns include `id`, `source`, `app`, `text`, `rating`, `date`, `video_id`, `context`. |
| `data/videos.csv` | YouTube videos the collector searched, so the same video is not fetched twice. |
| `data/clean.csv` | The 5,992 comments that mention a SIP and passed the hygiene checks. This is the list the model reads. |
| `data/loose.csv` | Extra comments that only weakly match. Used only if the strict list is too small (under 1,500 relevant comments). |
| `data/discarded_keyword_sample.csv` | A sample of comments the keyword step dropped, so a person can spot-check the filter. |
| `data/cache.json` | Saved model answers. A restarted tagger skips rows that are already here. |
| `data/relevant.csv` | Comments the model said are really about a SIP. Written when the relevance pass of a run finishes. |
| `data/discarded_relevance_sample.csv` | A sample the model marked “not about a SIP”, for a person to spot-check. |
| `data/final.csv` | The older labelled set. The dashboard does not mix these tags with the retag. |
| `data/final_v1_old_prompt.csv` | A copy of that older set. Do not overwrite it. |
| `data/final_retag.csv` | The only comments the dashboard scores and shows. Fields include `metric_scope`, `is_sip_instalment_issue`, `sip_outcome`, and `tenure_hint`. A note on the page says how many rows and which apps are covered. |
| `data/audit_sample.csv` | 105 comments a person labelled. 15 in each of 7 groups. |
| `data/audit_answers.csv` | The older model tags for those 105 comments. |
| `data/audit_retag.csv` | The temperature-0 rerun of those 105 comments. |
| `data/audit_retag_v2.csv` | A later pass on the same 105. Marked post-hoc, not an independent test. |
| `data/needs_review.csv` | Older unsure labels. The dashboard now lists unsure rows from `data/final_retag.csv`. |
| `data/ranking.csv` | Scores for each leak. Written by `4_score.py`. |
| `data/problem_candidates.csv` | The top 4 in-scope nodes by score, with counts and quotes. No best-problem label. |
| `data/evidence_summary.md` | The evidence note for a Google Doc. |
| `data/changes_log.csv` | Each scoring or prompt change, with before and after numbers. |
| `data/golden.csv` | An earlier hand-label sample. The 105-row check is `data/audit_sample.csv`. |
| `data/corrections.csv` | Notes when a model label was wrong. Columns: `row_id`, `text`, `ai_output`, `human_correction`, `reason`, `prompt_change`. |
| `data/sebi_log.csv` | How many displayed quotes had a fund or scheme name replaced with `[fund name]`. Detection may miss some names. |
| `data/funnel.json` | Counts at each step (raw, after cleaning, after labelling). |
| `data/model_used.json` | Which model the last tagging run chose. |

The comment files in `data/` are part of the project, so the dashboard still has them when it is hosted. `.env` and `.venv/` are not committed.

## Keys

Create `discovery-engine/.env`. One file only. Example (use your own keys, and do not commit the file):

```bash
NVIDIA_API_KEY=
GEMINI_API_KEY=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
HUGGINGFACE_API_KEY=
HF_MODEL=
YOUTUBE_API_KEY=
GROQ_API_KEY=
```

The tagger picks a model in this order:

1. `NVIDIA_API_KEY` — free Nemotron at `https://integrate.api.nvidia.com/v1`. Get a key at [build.nvidia.com](https://build.nvidia.com). This is the path used now.
2. `GEMINI_API_KEY` (and `_2`, `_3` as backups) — free Gemini, used when no NVIDIA key is set and `HF_MODEL` is blank.
3. A model name in `HF_MODEL`, or a short test of small Hugging Face instruct models, when a Hugging Face token has credits.
4. `GROQ_API_KEY` — Groq’s free tier, only if the steps above do not answer. Groq (groq.com) is a different company from Grok.

`YOUTUBE_API_KEY` is only needed for `1_collect.py` when YouTube is not skipped.

## Commands

Open Terminal, then run these from the `discovery-engine` folder. Do the setup once.

```bash
cd discovery-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To re-run collection or tagging on this machine, install the full set as well:

```bash
pip install -r requirements-full.txt
```

On a new terminal later, `cd` into the folder and run `source .venv/bin/activate` again before the Python commands. You should see `(.venv)` at the start of the line.

### Run the whole pipeline

Run these in order. Each one can take a long time. Wait for it to finish before the next.

```bash
python 1_collect.py
python 2_clean.py
python 3_filter_tag.py
python 4_score.py
python 5_evaluate.py
```

What you are waiting for:

| Command | What you will see | About how long |
| --- | --- | --- |
| `1_collect.py` | It prints counts as Play, App Store, and YouTube finish, then writes `data/raw.csv`. | A long run. Already done in this folder. |
| `2_clean.py` | It prints how many rows were dropped, then writes `data/clean.csv`. | Minutes. Already done. |
| `3_filter_tag.py` | First “Relevance cached …”, then “Tagged …”. Safe to stop and start again. It continues from `data/cache.json`. | The relevance sort is the faster half. Labelling every kept comment is the slow half (on the order of a couple of hours on the free NVIDIA key, if the key keeps answering). |
| `4_score.py` | A printed ranking, then `data/ranking.csv`. | Seconds, after labelling is done. |
| `5_evaluate.py` | Creates `data/golden.csv` the first time. Prints agreement only after you have filled in human labels. | Seconds. |

`3_filter_tag.py --limit 8` labels only the first 8 clean comments. That is a test. It still overwrites `data/final.csv`, so do not use `--limit` when you want the full result.

`python 3_filter_tag.py --retag-final` labels the rows in `data/final.csv` again at temperature 0 and writes `data/final_retag.csv`. It does not change `data/cache.json` or `data/final.csv`. `python 4_score.py` then ranks `data/final_retag.csv` when that file has the same number of rows.

### Add forum comments you found yourself

1. Open the page, copy the public text, and add one row to `data/manual_forums.csv`.
2. Put the site name in `source_label` (for example `Trustpilot`).
3. Put the date as `YYYY-MM-DD`, or leave it empty.
4. Refresh only the pasted rows, then clean again:

```bash
python 1_collect.py --skip-play --skip-app-store --skip-youtube
python 2_clean.py
```

Useful public places to read by hand: Trading Q&A (tradingqna.com), Value Research comments, and public Moneycontrol comments. Skip private WhatsApp, Telegram, and Facebook groups. Play Store, App Store, and YouTube are already collected by the script.

### Other collect flags

```bash
python 1_collect.py --groww-limit 20000 --competitor-limit 5000
python 1_collect.py --app-store-pages 10
python 1_collect.py --youtube-limit 20000
python 1_collect.py --skip-play
python 1_collect.py --skip-app-store
python 1_collect.py --skip-youtube
```

`--skip-play`, `--skip-app-store`, and `--skip-youtube` leave those sources as they already are and only merge new manual rows.

### Open the dashboard

```bash
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in a browser on this computer.

To open it from another device on the same Wi-Fi:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Use `http://localhost:8501` on this computer. On another device, use this computer’s local network address and port 8501. That address is not reachable from the public internet.

Leave that terminal open while you use the page. Press `Ctrl+C` in the terminal to stop the dashboard. Stopping the dashboard does not stop a tagging command that is running in a different terminal.

Refresh the browser after `3_filter_tag.py` or `4_score.py` finishes. The page reads the CSV files at refresh time.

## The six steps, in plain language

1. **Collect.** Save public comments. Already done.
2. **Clean.** Drop junk and keep comments that mention a SIP. Already done. 5,992 comments remain.
3. **Sort.** The first pass asked whether a comment was about a SIP. That result is already in the files. The retag does not repeat it.
4. **Label.** The retag sends one comment per call. The model records the tree box, the scope, the SIP outcome, whether a recurring instalment failed, a tenure hint, a confusion, an unmet need, a workaround, and a short quote copied from the comment. If it is unsure, the row is marked needs review and left out of the ranking.
5. **Rank.** Count which problems show up most. Score = how often × how serious × how fixable. Fixability is a human setting in `config.py`.
6. **Check.** `5_evaluate.py` prepares a sample for you. You write the human labels. The script does not invent them.

## The metric tree

Each labelled comment is placed in one box.

| Box | Plain meaning |
| --- | --- |
| A1 | The SIP was set up and the first instalment was debited. |
| A2 | Setup was finished. The person did not abandon it. |
| B1 | The 2nd and 3rd instalments succeeded. |
| B2 | The person did not cancel after the first statement or the first look at value. |
| C1 | They chose to pause, cancel, reduce, or redeem and leave. |
| C2 | The debit failed, the mandate expired, the bank changed, or the balance was too low. |
| C3 | A failed debit was noticed and fixed in time. |
| D1 | An instalment succeeded in the last 30 days (the month-12 “still running” sign). |
| E1 | Someone who had paused or failed started again. |
| none | The comment does not fit a box. |

## The dashboard

Title on the page: **SIP continuation discovery.**

### Overview

A bar chart of how many comments survived each step: raw, after hygiene, after the keyword gate, after the relevance check, and tagged with confidence. A second chart shows raw comments by source (Play Store, App Store, YouTube, manual). Under that, the working set by source.

Use this tab to see whether the pile is big enough to read. The caption names the model once labelling has written the funnel.

### Questions

Type one question and click **Find the answer**. The page does not list questions for you.

Examples that match a topic:

- Why do people start a SIP, and what do they expect?
- What do people do after they start?
- Why do people pause a SIP?
- What do they check, and how often?
- What confuses them in the app?
- What do they do outside the app?
- Why do some people continue and some stop?
- Who is commenting (income, age, who influenced them)?
- What do people still need?

The answer is a short lead, sometimes a small table, and up to a few quotes copied from comments. If a topic has no confident label yet, the lead says so. A question that does not match a topic is searched across the comment text instead.

The App dropdown defaults to Groww. Other choices are Other apps, YouTube with no app named, and All. Where the count is under 30, the page says **Too few comments to rely on**.

### Metric tree

The boxes from the table above, with a count on each. The biggest leak has a thick dark outline and the words **Largest leak**. A bar chart under the boxes shows the same counts.

The same App dropdown is on this tab and defaults to Groww. This tab does not show the small-sample line. Questions and Ranking still do when a count is under 30.

### Ranking

A table of leaks for all comments: how many comments (`n`), how common (`frequency`), how serious (`severity`), how fixable (`fixability`), and the score (frequency × severity × fixability). The chart highlights the largest leak.

The caption under the chart says fixability is set by hand in `config.py`. Severity is 3 when the SIP stopped and did not restart, 2 when it was paused, reduced, or the person is considering stopping, and 1 when they are confused or complaining but still continuing, including a failed debit that the comment does not say ended the SIP.

A tree box other than none needs the commenter's own SIP event. Trying to cancel, stop, pause, or reduce their own SIP counts as that event, even when the attempt does not succeed, and that comment is in scope. A question with no attempt, such as "will it affect me if I stop?", stays none. A1 and A2 are only for setting up a SIP or its first debit. A problem with an instalment of a SIP that is already set up is C2, or B1 when it is clearly the 2nd or 3rd instalment. A SIP that fails over and over with enough balance is C2.

Each label also says whether a recurring instalment failed (`is_sip_instalment_issue`: yes, no, or unclear) and what happened to the SIP (`sip_outcome`: ended, paused_or_reduced, continuing, or unclear).

The same App dropdown is on this tab and defaults to Groww. Under the main table, four versions of the top 5 nodes (excluding none) are shown for Groww and for All: Frequency × Severity × Fixability, Frequency × Severity, Frequency only, and Frequency × Fixability. The page says whether the top node changes.

Quotes on the page replace a detected fund or scheme name with `[fund name]`. The stored comment is unchanged. Detection may miss some names.

### Themes and segments

Four short tables: confusion points, unmet needs, workarounds outside the app, and a split of chosen stops versus failed debits by stage. Then short quotes grouped by tree box, and a mix of Groww, other apps, and YouTube.

**Segments** has a dropdown: `income_type`, `age_hint`, or `influenced_by`. Tick **Show unclear segment values** if you want the rows where the comment never said. Most comments do not state income or age, so those cuts are often empty. The source of the money (salary, savings, and so on) is not a label the model fills in.

### Try it

Paste one public comment and click **Tag this comment**. The model returns the tree box and the main fields, plus a confidence from 0 to 1 and a quote copied from your paste.

If confidence is under 0.60, or the model fails a check, the page says **Not sure, needs human review**.

This paste is not saved to the CSV files and is not added to the ranking. Use it to see how one comment would be read.

### Needs review

Comments the model would not stand behind: low confidence, a failed check, or no answer. The table reads those rows from `data/final_retag.csv`. These rows are excluded from the tree and the ranking.

Read a few of them. If the same mistake keeps showing up, add a row to `data/corrections.csv`.

## Before you trust a number

1. Read about 50 rows in `data/clean.csv`. Add a missing SIP word to `KEYWORDS` in `config.py` if real SIP comments were dropped, then run `python 2_clean.py` again.
2. Spot-check `data/discarded_keyword_sample.csv` and `data/discarded_relevance_sample.csv`.
3. Open `data/golden.csv` and fill the human columns **before** you study the model’s tags. Targets to aim for, once enough rows are labelled: at least 85% agreement on “is this relevant?”, and at least 75% agreement on the tree box.
4. Read `data/needs_review.csv`.
5. Record 2 or 3 wrong labels in `data/corrections.csv`.
6. If you disagree with a fixability score, edit `FIXABILITY` in `config.py` and run `python 4_score.py` again.

## Engine frozen

Frozen on 2 November 2026. The retag finished that morning at 2,477 rows, the same count as `data/final.csv`. Three hand-pasted comments were added later the same day, so `data/final_retag.csv` now has 2,480 rows. Groww is still 110 of those rows. Do not start another tagging run from this folder unless you deliberately unfreeze it.

Keep these files:

- `app.py`, `config.py`, `1_collect.py`, `2_clean.py`, `3_filter_tag.py`, `4_score.py`, `5_evaluate.py`, `requirements.txt`, `README.md`
- `data/final_retag.csv`, `data/final.csv`, `data/final_v1_old_prompt.csv`, `data/cache.json`
- `data/ranking.csv`, `data/problem_candidates.csv`, `data/evidence_summary.md`, `data/changes_log.csv`, `data/sebi_log.csv`, `data/funnel.json`
- `data/audit_sample.csv`, `data/audit_answers.csv`, `data/audit_retag.csv`, `data/audit_retag_v2.csv`, `data/corrections.csv`
- `data/raw.csv`, `data/clean.csv`, `data/manual_forums.csv`

## SIP help chat

The recovery screen is `mvp.py`. The instalment sits on the left and the chat sits on the right. The chat uses the NVIDIA model already set in `.env` (`nvidia/nemotron-3.5-super-vl-120b-a12b`). It does not call any other model.

```bash
cd discovery-engine
source .venv/bin/activate
streamlit run mvp.py --server.port 8502
```

Open [http://localhost:8502](http://localhost:8502). On the same Wi-Fi, use this computer's address and port 8502.

Other SIP questions are answered from the prompt when a note is still empty. News, returns, and fund details are refused. If you describe a missed debit, paying the SIP yourself, or setting autopay, the chat can fill the matching recovery screen. That path does not send a payment. Replies stay in the language of the message: English, Hindi, Hinglish, Punjabi, and the same rule for other scripts. The guardrails still refuse a fund pick, a buy or sell, a made-up NAV or return, and a made-up Groww button path. The support link in `chat/config.py` (`SUPPORT_URL`) is `TODO-VERIFY`.

To score the chat after the notes and the golden labels are filled:

```bash
python eval/run_eval.py
```

That scores the even rows in `eval/golden.csv` once and writes `eval/summary.json`. That file is not shown on the recovery page. Fifteen rows from the audit sample still need `expected_agent` and `expected_action`.

Chat text stays in the browser session. It is not written to a file. Anonymous turn counters are off.

The hosted prototype is [https://sd-nl-groww.streamlit.app/](https://sd-nl-groww.streamlit.app/). `NVIDIA_API_KEY` belongs in the host's secret settings, not in the repository.

## Publish later

When you host the dashboard, put the same keys in the host’s secret settings (Streamlit Community Cloud or a Hugging Face Space). Do not put them in the git repository. Keep the footer on every tab: “Analysis of public comments. Not investment advice.”
