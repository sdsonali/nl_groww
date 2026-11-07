# Groww: keep a first SIP running for 12 months

Product: **Groww**. Team: Growth.

Business metric: the share of first-time mutual-fund investors who still have an **active SIP** 12 months after starting their first one. Active means at least one successful instalment in the last 30 days.

This repository holds the discovery engine, the labelled public comments, the SIP instalment-help prototype, the eval files, and the slide deck. It does not recommend a fund or a stock. It does not use fear, FOMO, or urgency. Nothing here is investment advice, and the prototype does not move money.

The longer engine guide is [discovery-engine/README.md](discovery-engine/README.md). The slide deck is [discovery-engine/slides/NL_Groww.pdf](discovery-engine/slides/NL_Groww.pdf).

## What the work found

Public comments were collected, cleaned, and labelled one at a time with NVIDIA Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) at temperature 0. The engine was frozen on 2 November 2026. Counts are from `discovery-engine/data/funnel.json` and `discovery-engine/data/final_retag.csv`.

| Step | Count |
| --- | ---: |
| Raw comments | 54,550 |
| After hygiene | 27,843 |
| After the SIP keyword gate | 5,989 |
| After the relevance check | 3,220 |
| Retagged | 2,477 |
| Confident | 2,284 |
| Needs review | 188 |

Sources in the raw file: Play Store 45,645, YouTube 5,905, App Store 2,990, and 10 forum lines pasted by hand. Usernames are not stored. Reddit was not scraped.

The largest in-scope pattern is an involuntary stop: the debit failed, the mandate lapsed, the bank changed, or the balance was short (tree box C2). Groww is 110 of the 2,477 retagged rows. That is a pattern in public comments, not the true continuation rate for every Groww customer.

A hand-labelled check of 105 comments is in `discovery-engine/data/audit_sample.csv`. Places where a model label was rejected are in `discovery-engine/data/corrections.csv`. The evidence note is `discovery-engine/data/evidence_summary.md`.

## Two Streamlit apps

| App | File | What a person does |
| --- | --- | --- |
| Discovery dashboard | `discovery-engine/app.py` | Reads the labelled comments. Seven tabs: Overview, Questions, Metric tree, Ranking, Themes and segments, Try it, Needs review. |
| SIP help prototype | `discovery-engine/mvp.py` | One month's instalment on the left, chat on the right. A failed debit, a pending autopay, money already taken, or autopay switched off. Confirming does not send a payment. |

The chat calls NVIDIA at temperature 0, at most twice per turn. If it is unsure, it says so. A fund pick, a buy or sell, a return, a NAV, and news are declined. Account numbers typed into the chat are masked. A support handoff is a demo ticket that nobody receives.

## Run it locally

From this folder:

```bash
cd discovery-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `discovery-engine/.env` and put your own keys in it. That file is gitignored.

```bash
NVIDIA_API_KEY=
```

`NVIDIA_API_KEY` is what the dashboard "Try it" tab and the SIP help chat use. The other keys in the engine guide are only for re-running collection or an older model path.

```bash
streamlit run app.py
streamlit run mvp.py --server.port 8502
```

The dashboard is [http://localhost:8501](http://localhost:8501). The prototype is [http://localhost:8502](http://localhost:8502).

To score the chat after the golden labels are filled:

```bash
python eval/run_eval.py
```

`eval/summary.json` currently says the chat eval has not been run. Fifteen rows still need `expected_agent` and `expected_action`.

## Repository

```text
.
├── README.md                      This file
├── discovery_engine_plan.md       The build plan the engine was written from
├── runtime.txt                    Python 3.11 for Streamlit Community Cloud
└── discovery-engine/
    ├── app.py                     Discovery dashboard
    ├── mvp.py                     SIP instalment-help prototype
    ├── config.py                  Apps, SIP words, metric tree, fixability
    ├── 1_collect.py … 5_evaluate.py
    ├── chat/                      Router, safety checks, prompts, knowledge notes
    ├── eval/                      Golden questions and the chat scorer
    ├── data/                      Comments, labels, ranking, corrections
    ├── slides/                    Deck sources and NL_Groww.pdf
    ├── requirements.txt           Packages for a full local install
    └── requirements-deploy.txt    Smaller set used by the Dockerfile
```

`.env` and `.venv/` are not in the repository.

## Host on Streamlit Community Cloud

The code is in [sdsonali/nl_groww](https://github.com/sdsonali/nl_groww). Community Cloud deploys from that GitHub login.

1. Open [share.streamlit.io](https://share.streamlit.io) and continue with GitHub.
2. Create an app and paste the file URL.
   - Prototype: `https://github.com/sdsonali/nl_groww/blob/main/discovery-engine/mvp.py`
   - Dashboard: `https://github.com/sdsonali/nl_groww/blob/main/discovery-engine/app.py`
3. In Advanced settings, set Python to **3.11**.
4. In Secrets, add the NVIDIA key from your local `.env`. Do not commit it.

```toml
NVIDIA_API_KEY = "paste-the-key-here"
```

The dashboard can be read without a key. The "Try it" tab and the chat need the key. Both pages say they are not investment advice.
