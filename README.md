# Keeping the SIP alive

Why first-time investors quietly lose a SIP, and a small AI tool that helps them finish the month.

**Analysis of public comments and a prototype. Not investment advice.** Nothing in this project recommends a fund, a stock, or any investment decision. No fear, FOMO, or urgency is used. The prototype does not move money.

A Product Manager project on **Groww** (Growth Team). The discovery engine and the prototype were built in Cursor. Comment labels and the chat use NVIDIA's free hosted Nemotron model through an API. No model weights were downloaded.

The longer engine guide is [discovery-engine/README.md](discovery-engine/README.md). The slide deck is [discovery-engine/slides/NL_Groww.pdf](discovery-engine/slides/NL_Groww.pdf). The evidence note is [discovery-engine/data/evidence_summary.md](discovery-engine/data/evidence_summary.md).

**Live prototype:** [https://sd-nl-groww.streamlit.app/](https://sd-nl-groww.streamlit.app/)

That address should be the SIP help screen (`discovery-engine/mvp.py`), not the comment dashboard. A clearer subdomain, such as `sip-instalment-help`, is easier for a mentor to recognise. Streamlit lets you change it under the app settings. The old address stops working after a change, so update this README and the submission if you rename it.

## TL;DR

- **The goal:** more first-time mutual fund investors should still have an **active SIP 12 months** after starting. Active means at least one successful instalment in the last 30 days.
- **The problem was not given.** It had to be discovered.
- **Discovery engine:** public comments were collected and tagged against a metric tree. The file now has **2,480** tagged rows. The ranking uses the **2,287** confident ones.
- **What the comments show:** the largest in-scope leak is a failed or stuck instalment (C2, **333** confident comments). Only **0.9%** of those 333 say the SIP ended. Groww is **17** of them. That is a pattern in public comments, not a Groww rate.
- **What came next:** eight interview notes, then a prototype that names the break and offers one safe next step.
- **What is still open:** the chat has not been scored. Fifteen golden rows still need `expected_agent` and `expected_action`. A write-up of three people using the live app is not in this repo.

## 1. The problem

Starting a SIP takes a few taps. Staying with it is harder. Months pass, the first statements are hard to read, and a debit that does not finish can become a stop the person did not choose.

**The question:** why does continuation break for a first-time investor who started with good intent?

Rules kept throughout:

1. Never recommend a specific fund or stock.
2. Never use fear, FOMO, or urgency.
3. Never present the output as investment advice, and say so on screen.
4. Never ask for PAN, account numbers, or portfolio screenshots.
5. "Investors stop when markets fall" is not the answer this work accepts.

## 2. The journey

| Part | What was done | Where to look |
| --- | --- | --- |
| 1. Discovery engine | Public comments, tagged onto a metric tree | Section 3 |
| 2. Metric breakdown | 12-month active SIP split into start, settle-in, stay, month 12, and recovery | Section 3.3 |
| 3. User research | Eight interview notes. No survey | Section 4 |
| 4. Problem definition | Segment, moment, root cause, workarounds | Section 4 |
| 5. MVP | SIP instalment recovery, with a quality gate | Section 5 |
| 6. MVP testing | Not written up in this repo | Section 5.5 |
| 7. Success metrics | Business metric, leading indicators, guardrails, AI quality | Section 6 |
| 8. Risks | Why it might fail, and what is already in the build | Section 7 |

The chain is: business metric, product outcomes, AI discovery, primary research, problem definition, MVP.

## 3. The discovery engine

### 3.1 How it works

| Step | What happens | Done by |
| --- | --- | --- |
| Collect | Play Store, App Store, and YouTube, plus forum lines pasted by hand. Usernames stripped. | Code |
| Clean | Drop duplicates, spam, very short text, and comments that never mention a SIP | Code |
| Sort | Is this comment about starting, continuing, pausing, stopping, or failing a SIP? | AI |
| Tag | Place it on the metric tree, with scope, outcome, confusion, workaround, and a copied quote. Low confidence goes to needs review. | AI |
| Rank | Score = how often × how serious × how fixable in the app. Fixability is set by hand. | Code |
| Check | A 105-comment golden set. Disagreements are written down and the instructions are rewritten. | PM |

Comments mix Hindi and English. A keyword count cannot tell "my SIP failed" from "will my SIP fail?" or "I want to start a SIP". When the model is unsure, the row is left out of the ranking.

**Model:** `nvidia/nemotron-3.5-super-vl-120b-a12b`, one comment per call, temperature 0. Hugging Face and Gemini free tiers were tried first and ran out of credit or quota.

### 3.2 Volumes in the files now

`discovery-engine/data/funnel.json` and `discovery-engine/data/final_retag.csv`, after three hand-pasted comments were added on 2 November 2026. The earlier freeze line was 54,550 raw comments and 2,477 tagged rows. Those three extra rows are in `data/changes_log.csv`.

| Step | Count |
| --- | ---: |
| Raw comments | 54,553 |
| Play Store | 45,645 |
| YouTube | 5,905 |
| App Store | 2,990 |
| Hand-pasted lines | 13 |
| After hygiene | 27,846 |
| After the keyword gate | 5,992 |
| After the relevance check | 3,220 |
| Tagged | 2,480 |
| Confident (`status` ok) | 2,287 |
| Needs review | 188 |
| Dropped | 5 |

Of the 2,480 tagged rows, **110 are Groww**. The rest are Zerodha Coin, ET Money, Kuvera, Paytm Money, INDmoney, YouTube with no app named, and a few pasted lines. Competitors and YouTube are a comparison set. Reddit was not scraped. Four of the 13 pasted lines are marked Reddit because someone had already read them.

### 3.3 The metric tree

Every tagged comment lands in one box.

```text
12-month active SIP
├── A. Start well           A1 first instalment debited    A2 setup completed or stuck
├── B. Settle in (months 1-3)  B1 2nd and 3rd instalments  B2 reaction to the first statement
├── C. Stay through             C1 chose to pause, cancel, or reduce
│                               C2 failed without the person choosing
│                               C3 a failed debit was noticed and fixed
├── D. Reach month 12           D1 an instalment in the last 30 days
└── E. Recovery                 E1 paused or failed, then restarted
```

The ranking below uses confident rows only. In-scope confident rows: **837**.

| Box | Confident, in scope | Share of 837 |
| --- | ---: | ---: |
| C2 failed or stuck instalment | 333 | 39.8% |
| C1 chose to stop, pause, or reduce | 246 | 29.4% |
| A1 first debit | 128 | 15.3% |
| A2 setup | 74 | 8.8% |

### 3.4 What the engine found

| Finding | Evidence in the current files |
| --- | --- |
| Failed or stuck instalments are the largest in-scope leak | Confident in-scope C2 is 333, score 0.44. It ranks above C1. |
| Those C2 rows are mostly recurring instalments | All 349 rows tagged C2: 344 yes, 4 unclear, 1 no. Of the 333 confident C2 rows: 328 yes, 4 unclear, 1 no. |
| Almost none of the confident C2 rows say the SIP ended | 3 of 333 (0.9%) ended. 289 of 333 (86.8%) are tagged continuing. |
| An earlier pass could not name a reason for most pause-or-stop comments | On 374 comments, before the final retag: 109 "cancelled, no reason given" and 143 with no matching reason phrase. That is 252 of 374. It is not a rate on the 2,480-row file. |
| Groww counts are too small to quote as a rate | Confident Groww rows: 95. Groww C2 is 17. Groww C1 is 12. The page says a count under 30 is too few to rely on. |
| The top node depends on the formula | On all apps, C2 leads three of the four score versions. On Groww alone, C1 leads frequency × severity × fixability, and C2 leads frequency alone. |

What the failed-instalment quotes describe: a low balance on the debit date, autopay that did not run, a mandate that fails again, money that left the bank but is not showing as units, and a status that still says failed after a payment.

One comment said a visible pause option kept them from cancelling. The prototype does not make cancel or pause harder.

### 3.5 How the labels were checked

1. **Golden set.** 105 comments in `data/audit_sample.csv`, 15 in each of 7 groups. Labels were drafted with model help, then reviewed row by row.
2. **First comparison.** `human_correct (yes/no)` is yes on **47 of 105** rows (44.8%). That column is stage agreement.
3. **What was wrong.** Six corrected rows are in `data/corrections.csv`. All six were moved to `none`: a question, a hypothetical, a wish to start, an affordability worry, and two complaints about money that did not come out after a cancel.
4. **The instructions were rewritten.** A tree box other than `none` needs something that happened to the person's own SIP. Odd rows were the tune set (53). Even rows were the test set (52).
5. **The test set, two runs.**

| Test set (52 rows) | Before | After |
| --- | --- | --- |
| Stage agreement | 24 of 52 | 40 of 52 at temperature 0.1, 44 of 52 at temperature 0 |
| "Not a SIP event" | 7 of 35 | 28 of 35, then 31 of 35 |
| Stage C agreement | 14 of 14 | 10 of 14 on both runs |

Stage agreement rose. Stage C agreement fell. Some real cancel attempts and instalment problems were pushed out, so a later rule was added and all rows were retagged. `data/audit_retag_v2.csv` is that later pass on the same 105. It was not scored, and it is not an independent test.

6. **Severity was retied to what happened to the SIP.** A failed debit that the comment does not say ended the SIP is no longer scored as if the SIP had stopped. C2's score moved from 1.37 on the older file to 0.44 on the current confident rows.
7. **A scope flag** separates staying in a SIP from leaving the platform. On all 2,480 rows: in scope 863, exit 20, other platform complaint 512, unclear 1,085 (43.8%). The unclear share was not fully rechecked by hand.
8. **The change log** is `data/changes_log.csv`. Each row has a before and an after.

38 retagged rows have an empty `tenure_hint`. They were kept from before the shorter prompt.

## 4. From the comments to a problem

**Primary research.** Eight interview notes are in the research slide (`discovery-engine/slides/02-research.html`). No survey was fielded. The notes do not record how people were recruited. They do not include PAN, account numbers, or portfolio screenshots. Quotes on the slide are framed from the notes, not transcripts.

| Person | What they described |
| --- | --- |
| Kritika, 30 | Groww had been working. After a bank change there was no form and no email. The instalment failed and units were not allotted. Closest match to this prototype. |
| Madhuri, 26 | Money left the bank and did not show in the NAV. In-app help and support both stopped short. |
| Ruchi, 26 | She pays the SIP by hand. Autopay appears only after a payment she has already made. |
| Manas, 23 | Wants help on the page he already has open, then a person if that is not enough. |
| Akshay, 22 | A ₹500 SIP, started on a friend's recommendation. Cancelled after four months because he could not read the early result. |
| Akshay, age not recorded | After a redeem, he cannot see the path from the fund house back to the bank. May be the same person. This job is not in the prototype. |
| Tarun, 33 | Stops and redeems when he sees a small gain. Said the charges felt high. Not this leak. |
| Rohan, age not recorded | Bought a SIP that was in a loss and has not cancelled. Looks only when he happens to open the app. A return alert would become advice, so it is out. |

**Where the notes agree with the engine.** A debit that fails, a bank change with nowhere to update it, and money that has left but is not showing are the same break as C2. Akshay's cancel after an unreadable statement is a chosen stop, which the comments also contain, and it is not the leak this prototype takes first.

**Where a comment count was not enough.** The engine cannot say why a quiet first-year investor stops when they never write a review. The notes add that: an unreadable first statement, a missing bank form, and autopay that only appears after a manual payment.

| | |
| --- | --- |
| Target segment | A first-time mutual-fund SIP investor on Groww, in the first 12 months, with a small instalment. Kritika is the closest interview match: the SIP was already set up, then the bank changed. |
| The moment | This month's instalment did not finish, and the screen does not say which of the four breaks it was or what to do next. |
| Product outcome | The failed month is completed, or the person is told not to pay a second time because the money has already left. |
| Root cause | The failure is hard to read, and the safe next step is not on the page. Three missed monthly instalments can be treated as a discontinued SIP. |
| Workarounds in the notes | Search, pay the month by hand, wait for support, or leave the app. |
| User value | Finish this month, or avoid paying twice, without a lecture about markets. |
| Business value | An investor who still has a successful instalment in the last 30 days is the person the 12-month metric counts. |

## 5. The MVP: SIP instalment recovery

### 5.1 What it is

`discovery-engine/mvp.py` is one Streamlit screen. The sample instalment is on the left. The chat is on the right. It is not a sidebar, and it is not a separate page for every step.

The sample SIP is ₹2,000, due on the 5th, from a bank account ending 4821. The next date stays 5 December. Four breaks:

- The bank rejected the debit.
- Autopay did not send it.
- Money already left the bank, and units are not showing. There is no pay button on this path.
- UPI autopay is off before the debit day.

A bank-change form accepts an optional account-holder name. Bank, account number, phone, and address stay masked. Confirming does not send a payment. The page says so.

### 5.2 The chat

The chat opens with a question, not a menu of funds. A written message goes to NVIDIA at temperature 0, at most two calls. The router can send it to an instalment, controls, learn, or scheme note. News, returns, and fund details are refused in the pipeline. A second low-confidence reply, or a second decline, becomes a handoff.

After an answer, the screen asks **"Are you satisfied with the response?"** Yes ends that thread. **No, connect me with support** builds a demo ticket. Nobody receives it. The support link in `chat/config.py` is still `TODO-VERIFY`.

The chat does not show a confidence percentage. If it is unsure, the reply says so and points at a source when the note has one. A number under 0.60 is treated as unsure inside the pipeline.

A SIP growth chart, a return alert, and a redemption tracker are not in this prototype.

### 5.3 Where the model earns its place

The four chips work with no model call. A typed question is where the model is needed: the wording is messy, often Hinglish, and the bank message does not match the chip labels. A fixed menu would still show the four breaks. It would not answer a typed question, and it would not decline a fund.

### 5.4 The quality gate

- Outputs are meant to be scored against `eval/golden.csv`. `eval/summary.json` says that score has **not been run**. Fifteen rows still need labels.
- Unsure answers fall back instead of guessing.
- Fund names, a buy or sell, a made-up NAV, and a made-up return are blocked.
- The footer says the screen is not investment advice.
- There is no fear, FOMO, or urgency copy.
- There is no daily cap in the code. A host limit would be a later control.

### 5.5 What users said about the live app

A test of the deployed screen with three people from this segment is **not written in the repo**. The eight interviews above are discovery notes. The slide brief says they are not a test of the demo. Do not fill this section with those quotes and call it a usability test.

**Links**

- Prototype: [https://sd-nl-groww.streamlit.app/](https://sd-nl-groww.streamlit.app/)
- Code: [https://github.com/sdsonali/nl_groww](https://github.com/sdsonali/nl_groww)
- Discovery dashboard: run `streamlit run app.py` locally, or deploy `discovery-engine/app.py` as a second app
- Evidence note: [discovery-engine/data/evidence_summary.md](discovery-engine/data/evidence_summary.md)

## 6. How to know it works

| Level | Metric | Definition |
| --- | --- | --- |
| Business | 12-month SIP continuation | Share of first-time investors with a successful instalment in the last 30 days, 12 months after their first SIP |
| Leading | Failed instalments recovered | Share of failed instalments followed by a successful one before the next due date |
| Leading | Told not to pay twice | When the money has already left, the person does not send a second payment |
| Leading | Time to recovery | Days from the failed instalment to a successful one |
| Guardrail | Cancel or pause friction | No extra taps added to cancel or pause |
| Guardrail | Advice in the output | No fund name, no return, no buy or sell |
| AI quality | Agreement with the golden set | Share of scored turns whose action and route match `eval/golden.csv` |
| AI quality | Safe fallback | Share of low-confidence turns that decline or hand off |
| AI quality | Confident and wrong | Turns the gate let through that a reviewer marks wrong |

The chat score is not available yet. Do not quote one.

## 7. Risks

| Risk | What is already true |
| --- | --- |
| Comments are public, loud, and mostly not Groww | The problem was checked against the interview notes. Groww C2 is reported as 17 comments, never as a rate. |
| A failed instalment may not be why people quit | Treated as the leak to test, not as a proven cause of the 12-month metric. |
| The chat explains the wrong break | Unsure replies fall back. A second miss hands off. The golden-set score is still not run. |
| It looks like advice | Fund and return language is blocked. The page says it is not investment advice. |
| It makes leaving harder | Cancel and pause are not made longer. A visible pause is treated as a way to stay, not a trap. |
| Personal data | Public comment text only. The prototype does not ask for PAN or a portfolio screenshot. Typed account-like strings are masked. |
| The support link is wrong | `SUPPORT_URL` is `TODO-VERIFY`. The handoff is a demo ticket. |
| Small Groww sample | Counts under 30 are labelled too few to rely on. |

## 8. Limits

- Public comments over-represent people who are angry or pleased. Quiet drop-offs rarely write a review.
- First-12-month investors are under-represented.
- 110 of 2,480 tagged rows are Groww. 95 of those are confident.
- The golden set was drawn from the engine's own themes, so it checks tags the engine already made. It does not measure comments the engine never kept.
- Two runs of the same prompt differed by as many as 4 test rows. Ranges are in section 3.5.
- Play Store collection uses `google-play-scraper`, which is not an official Google API.
- Reddit was not scraped.
- 1,085 of 2,480 rows are scope `unclear`. That share was not fully checked by hand.
- 38 rows have an empty tenure hint.
- The ₹40 crore line in the working deck is an assumption. It is not a result and it is not Groww's loss.

## 9. Repo guide

```text
.
├── README.md                         This file
├── discovery_engine_plan.md          Build plan
├── runtime.txt                       Python 3.11 for Streamlit Community Cloud
└── discovery-engine/
    ├── app.py                        Comment dashboard
    ├── mvp.py                        SIP instalment recovery
    ├── config.py                     Apps, SIP words, metric tree, fixability
    ├── 1_collect.py … 5_evaluate.py  Collect, clean, tag, rank, sample
    ├── chat/                         Router, safety checks, prompts, notes
    ├── eval/                         Golden chat rows and the scorer
    ├── data/                         Comments, labels, ranking, corrections
    ├── slides/                       Deck sources and NL_Groww.pdf
    ├── requirements.txt              Full local install
    └── requirements-deploy.txt       Smaller install for a container
```

Run it:

```bash
cd discovery-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Put keys in `discovery-engine/.env`. That file is not in git. The hosted app needs `NVIDIA_API_KEY` in the host's secrets, in this form:

```toml
NVIDIA_API_KEY = "paste-the-key-here"
```

```bash
streamlit run app.py
streamlit run mvp.py --server.port 8502
```

The dashboard is [http://localhost:8501](http://localhost:8501). The prototype is [http://localhost:8502](http://localhost:8502).

Evidence files: `data/changes_log.csv`, `data/corrections.csv`, `data/audit_sample.csv`, `data/funnel.json`, `data/final_retag.csv`, `data/evidence_summary.md`.

## 10. What is next

1. Score the chat once the fifteen golden rows are labelled.
2. Watch three people from this segment use the live screen on one failed month, and write that up separately from the discovery interviews.
3. Replace the assumed unrecovered-instalment rate with an internal one before anyone quotes a rupee figure.
4. Verify the Groww help link before a handoff is described as support.

## Data and privacy

Public text only. The labelled file has no username, email, or handle column. A scan of that comment text found no email address and no @handle. Two public business addresses in `data/videos.csv` were replaced with `[email]` before the repo was pushed. Fund names in quotes on the dashboard are replaced with `[fund name]` when the list matches. The list can miss a name.

Interviewees were not asked for PAN, account numbers, or portfolio screenshots.

This project analyses public comments and demonstrates a prototype. It is not investment advice.
