# Groww SIP slides — brief for edits

Use this file as the source of truth when changing the deck. Edit the HTML slide named in the request. Keep every number, name, and rule below. Do not invent a survey, a rate, an age, or a competitor feature we did not count. Do not restyle the other slides.

Ten pages are in the PDF. Page 2 is the search engine. Page 10 is why the solution might fail. Edit the HTML files. Do not edit `deck.html` or `sip-help-deck.pdf`. Those were an earlier draft and are not the deck.

Paths below are inside `discovery-engine/`. The shareable PDF is `slides/NL_Groww.pdf`. A copy also sits on the Desktop as `NL_Groww.pdf`. `groww-sip-slides.pdf` is the same file. After an HTML edit, reprint that page and rebuild the combined PDF. Do not treat the PDF as the file to edit. Public links for the engine, the demo, and the evidence log are still blank on purpose. Add those links when they exist. Do not invent a URL.

Combined PDF: `discovery-engine/slides/NL_Groww.pdf` (10 pages, in this order).

| Page | HTML | PDF |
| --- | --- | --- |
| 1 | `slides/01-problem.html` | `slides/01-problem.pdf` |
| 2 | `slides/02-discovery.html` | `slides/02-discovery.pdf` |
| 3 | `slides/02-research.html` | `slides/02-research.pdf` |
| 4 | `slides/03-true-problem.html` | `slides/03-true-problem.pdf` |
| 5 | `slides/04-problem-framing.html` | `slides/04-problem-framing.pdf` |
| 6 | `slides/05-mvp-scope.html` | `slides/05-mvp-scope.pdf` |
| 7 | `slides/06-solution-flow.html` | `slides/06-solution-flow.pdf` |
| 8 | `slides/07-wireframes.html` | `slides/07-wireframes.pdf` |
| 9 | `slides/08-system-metrics.html` | `slides/08-system-metrics.pdf` |
| 10 | `slides/10-risks.html` | `slides/10-risks.pdf` |

Each HTML file is one slide, 1366×768, cream background `#f6f1e8`, navy header `#123a63`, orange labels `#c65a12`. Keep the headings listed in the rules. Body, captions, and the footer are 14px. Open an HTML file in a browser. After an edit, reprint that page with headless Chrome (`--print-to-pdf`, page size `14.229in 8in`, no header/footer) and rebuild `NL_Groww.pdf` from the ten PDFs in the order above. The wireframe image on page 8 is `slides/wireframe-final.jpg`. Do not swap it for an enlarged copy. File names after page 2 were not renumbered.

## Rules

- Not investment advice. Do not name a fund or stock to buy, sell, stop, or restart. Do not predict returns. No fear, FOMO, or a countdown.
- No survey was fielded. Do not invent survey percentages.
- 17 Groww C2 comments are under 30. Say “pattern, not a Groww rate.” Never multiply 39.8% by 10.03 million.
- The ₹40 crore line is an assumption. Both rates (5% miss, 40% still open) must stay next to it. It is not a measured loss and not a target.
- Comment counts are comments, not customers.
- Do not invent ages. Kritika is 30 (given as age group 30). Rohan’s age was not recorded. The redemption note is also named Akshay and has no second age.
- Interview lines are framed from notes, not transcripts. Do not add facts the person did not say.
- The illustration `slides/sip-failed-debit.jpg` is not a photo of Kritika or anyone else.
- Reddit rows are in `data/manual_forums.csv` and are not inside the 333 C2 comments. Do not give Reddit a percentage.
- Do not recite a Groww support phone. Do not claim this screen takes a fee or a share of ₹46,624 crore.
- “Disc. / done” includes SIPs that finished their term, not only failures.
- NACH 25.2% is EMI, SIP, insurance, and bills together, not SIPs alone.
- Headings, in order: A failed debit stops the SIP before anyone chooses to leave; Search engine; Involuntary leaks: failed debit, expired mandate, bank change, low balance; Understanding users: insights, common persona and primary/secondary research; Problem prioritization; MVP scope and feature prioritization; Solutioning and user flow; Wireframe ideation; System design, success metrics, user journey map; Risks and mitigations. Every heading starts at the left, with the same padding.
- Body type stays at 14px. If a line no longer fits, cut the line. Do not drop below 14px.
- Do not invent a usability test, a quote, a completion rate, or a satisfaction score. The eight interviews are discovery notes. They are not a test of the demo.

## Numbers that are already checked

Confident in-scope comments: 837. One box each. Source: `data/final_retag.csv`, status ok, metric_scope in_scope.

| Box | Meaning | Count | Share of 837 |
| --- | --- | ---: | ---: |
| C2 | Debit failed, mandate expired, bank changed, or balance short | 333 | 39.8% |
| C1 | Chose to pause, cancel, reduce, or redeem and leave | 246 | 29.4% |
| A1 | First instalment | 128 | 15.3% |
| A2 | Setup | 74 | 8.8% |
| Rest | D1 22, none 11, E1 7, B1 7, B2 5, C3 4 | 56 | 6.7% |

Inside the 333 C2 comments:

- Still continuing: 289 (86.8%). Ended: 3 (0.9%).
- An instalment of a SIP already set up: 328 (98.5%).
- Play Store 188 (56.5%), YouTube 103 (30.9%), App Store 40 (12.0%), Quora + Pissed Consumer 2 (0.6%).
- Apps named in those 333: Zerodha Coin 122 (36.6%), ET Money 52 (15.6%), Paytm Money 21 (6.3%), Groww 17 (5.1%), Kuvera 13 (3.9%), INDmoney 3. The other 103 are YouTube comments with no app named. INDmoney is too few for its own row. These are shares of the 333 comments, not customers and not market share.
- C3, fixed in time, is 4 of 837 (0.5%).

Market, all AMFI unless noted:

- Sep 2026 collection ₹32,490 crore. Accounts outstanding 10.89 crore. SIP assets ₹17.86 lakh crore.
- Sep 2026: 63.26 lakh new, 49.68 lakh discontinued or completed.
- FY26: 719.22 lakh new, 679.75 lakh discontinued or completed (94.5% of new). Includes finished tenures.
- Apr–Sep 2026 new, lakh: 50.71, 54.16, 55.51, 61.44, 66.4, 63.26.
- Apr–Sep 2026 discontinued or completed, lakh: 51.29, 51.7, 50.64, 50.3, 53.82, 49.68. April is the month discontinued was higher than new.
- Monthly SIP book: ₹25,926 crore in March 2025 to ₹32,087 crore in March 2026. AMFI Factbook 2026. Up ₹6,161 crore, 23.8%.
- Groww FY26 annual report: 10.03 million mutual-fund active users, SIP inflows ₹46,624 crore, over 43% of new SIPs in India.
- NACH Sep 2026: 25.2% of recurring debits unpaid (4.9 crore of 19.6 crore). Not SIPs alone.
- NCFE 2019: 27% of Indian adults financially literate. No newer NCFE rate.

Guesstimate, assumptions only: 5% of 10.03 million miss one instalment = 5.0 lakh. 40% of those still open = 2.0 lakh. At ₹2,000, about ₹40 crore for one month.

## Interviews

Closest match is Kritika, 30, working professional. Groww had been working. When her bank changed there was no form and no email. The ongoing SIP failed and the NAV was not allotted. She wanted to enter the new bank details on the page so the money would be debited and allotted.

Madhuri, 26, working professional. Same problem, second break. The money left her bank and did not show in the NAV. In-app AI and support both stopped short. She wants a bot that tries first, then a person.

Ruchi, 26. The app works, but she pays the SIP by hand every time. Autopay appears only after a payment. She wants that option on the page. Beside C2, not the lead.

Manas, 23, student. Started on Groww after researching, for long-term saving. Wants a bot on whatever page is open, and a way to support when something is wrong. Do not turn his goal into a fund recommendation.

Akshay, 22, college student. Friend’s recommendation, ₹500 SIP, cancelled after four months because he could not read the data. Tried YouTube. Later. Do not tell him which fund to buy.

Akshay, redemption. No second age. Cannot see whether the fund house has processed a redeem, or when it reaches his bank. He moved one or two SIPs. Later. Not in this release.

Tarun, 33. Many SIPs. Books a small gain and said the charges felt high. Do not tell him to stay or leave. Later.

Rohan. Age not recorded. Has not cancelled a SIP that was in a loss. Rarely looks. Wants a status, not a return alert. Later.

## What each slide says

### Page 1 — the problem, the audience, the market

Header: A failed debit stops the SIP before anyone chooses to leave.

Two breaks, neither is “they chose to leave.” Involuntary leak: 333 of 837 (39.8%), and only 0.9% of those 333 say the SIP ended. Lack of knowledge: setup questions, and an interview where the person could not read the data and then cancelled.

Why it becomes a stop: people search outside the app; three misses can be treated as discontinued; NACH 25.2% is the wider recurring-debit figure, not SIPs alone.

Who: a first-time mutual-fund investor on Groww whose SIP should still have one successful instalment in the last 30 days, a year after they started.

TAM / SAM / SOM on one scale in crore: 10.89 crore accounts, 1.00 crore users (10.03 million), about 0.02 crore instalments. SOM is the assumption above.

Market-trend chart, Apr–Sep 2026, new versus discontinued or completed. Market landscape stats and the Sep 2026 / FY26 pairs. Comment bars for C2, C1, A1, A2. Four-step path from a missed debit to three misses. Illustration of a failed debit.

Footer: public comments, not investment advice, retag of 2,480 rows, market figures are the months named, not a forecast.

### Page 2 — search engine

Header: Search engine.

Why: of people who start a mutual-fund SIP, how many still have one running 12 months later? Active means one successful instalment in the last 30 days. Public comments were sorted onto that path before the interviews and the prototype. A reading aid. Not a customer rate. Not a fund recommendation.

Overview graph: comments remaining after each step, raw comments by source, then the working file by source. Counts from `data/funnel.json` and the current `data/final_retag.csv`: collected 54,553 (Play Store 45,645, YouTube 5,905, App Store 2,990, 13 pasted by hand, 4 of them Reddit excerpts already read). Reddit was not scraped. No usernames. After hygiene 27,846. Mentions a SIP 5,992. About a real SIP 3,220. Tagged file 2,480: 2,287 confident, 188 needs review, 5 dropped. The collection log’s last tagged count was 2,477. The slides use 2,480.

Finding: 333 of 837 confident in-scope comments (39.8%) are the involuntary leak. 289 of 333 (86.8%) still continuing. 3 (0.9%) ended. Groww is 17 of the 333, a pattern, not a rate.

Metric tree: A1 and A2 setup and first debit, B months 1–3, C1 chosen stop, C2 failed debit, C3 miss fixed in time, D1 successful instalment in the last 30 days, E1 restart, none everything else. Largest in-scope leak is outlined. On this file that is C2. Ranking is frequency × severity × fixability. Fixability is set by hand. Severity stays 1 when the SIP is still continuing, including a failed debit the comment does not say ended. The app menu opens on Groww. Under 30 comments is too few to rely on.

Questions: type one question and press Find the answer. A short lead, sometimes a table, and quotes copied from comments. Groww, other apps, YouTube with no app named, or all. A question that does not match a topic is searched in the comment text. Segments (income, age, who influenced them) are mostly unstated.

Working file by source, of 2,287 confident comments: Play Store 1,145, YouTube 975, App Store 160, pasted by hand 7. YouTube names no app. Zerodha Coin 501, ET Money 339, Kuvera 211, Paytm Money 112, Groww 95, INDmoney 47. Groww’s 95 are every confident Groww comment, not the 17 failed-debit comments.

Try one comment: Tag this comment. Under 0.60 confidence, or a failed check, the page says not sure and needs human review. The paste is not saved and is not added to the ranking. The 188 unsure rows stay out of the tree and the ranking. Themes are confusion points, unmet needs, workarounds outside the app, and chosen stops against failed debits.

Hand check: 105 comments, 15 in each of 7 groups. First stage agreement 47 of 105. Six misses became the prompt rule: a question, a hypothetical, a wish to start, or money not back after a cancel is not that person’s failed or cancelled SIP. Odd 53 tuned the prompt. Even 52 were the test, once, at temperature 0: stage 44 of 52 (was 24), exact tag 40 of 52 (was 21). Stage C fell from 14 of 14 to 10 of 14. Then the full file was retagged. Frozen 2 November 2026. NVIDIA, one comment per call. Not a survey. Do not quote the tune-set scores. Do not quote a chat-model score.

### Page 3 — user research

Header: Involuntary leaks: failed debit, expired mandate, bank change, low balance.

Hypothesis, in detail: the SIP is not a chosen stop. It breaks in one of four ways, and those four are one dead end today. 333 of 837 (39.8%) are that leak. 86.8% of the 333 are still continuing. Only 0.9% ended. A bank change needs a form (Kritika). Money already left needs a wait or a return, not a second debit (Madhuri). A failed debit can be paid once. An expired mandate is a renew, not a new SIP. The bet is that naming the cause and one safe step finishes this month before the next due date and before three misses. Not measured. No survey.

Competitive research, added on this slide: public C2 comments, not a product audit and not a customer rate. Of the 333: Zerodha Coin 122 (36.6%), ET Money 52 (15.6%), Paytm Money 21 (6.3%), Groww 17 (5.1%), Kuvera 13 (3.9%). YouTube with no app named is 103 and is not a player in the table. INDmoney is 3, too few for a row. What people wrote: Coin, money left and the SIP did not update; ET Money, auto-debit missed despite balance and bounce charges; Paytm Money, autopay does not run; Groww, declined or stuck for a month, and 17 is a pattern not a rate; Kuvera, debited but NAV not allotted, or mandate done and the debit not cut. The gap is the same: the comment does not get a named cause and one next step that cannot charge them twice. Do not claim we opened each app and found a missing screen.

Four donuts: 39.8%, 29.4%, 15.3%, 8.8%. These are comments, not a survey.

Primary persona: Kritika, with the illustration labeled as not her photo. Madhuri marked “same problem.” Ruchi, Manas, Akshay 22, redemption Akshay, Tarun, and Rohan are the others. Later jobs stay later.

Pain: bank change with nowhere to update it; debit not in the NAV; autopay hidden until a payment; unreadable screen.

Opportunities: a bank form on the page; a bot that answers first and then reaches support. Return alerts and “should I stop?” stay out.

Quotes, framed from notes: Kritika, Madhuri, Ruchi.

Behaviour as above. NCFE 27% is a wider benchmark, not these eight people.

Impact: 333 comments, three misses, 10.03 million users as the reachable base, not a loss figure. NACH 25.2% is on this page and on page 1.

### Page 4 — understanding users

Header: Understanding users: insights, common persona and primary/secondary research.

Framing: this is not “they chose to leave.” The page does not separate a bank change, a failed debit, and money that has already left.

Job line on this slide only: when this month’s instalment does not land, help me see what happened and finish it, or tell me not to pay again. If the bank changed, let me update it on the page. Do not add this job line back onto slide 4. It was removed from slide 4 on purpose.

How we know: 333 of 837, Kritika, Madhuri, the three-miss rule. No survey. 17 Groww comments are not a rate.

Why now: FY26 discontinued or completed were 94.5% of new SIPs. Groww opened over 43% of new SIPs. Kritika’s bank change is current.

Who: Kritika first, Madhuri as the second break. Not someone deciding whether to buy, sell, or stop.

Secondary research, no names:

- Play Store, Groww, 16 Aug 2026: “I invest in SIP. Money debited but didn’t allotted, and the money is also not refunded.”
- YouTube, 18 Feb 2026, missed-SIP video: “SIP fail bata rha hai. Refund kab aayega.” https://www.youtube.com/watch?v=YnmMfVU3l94
- YouTube, 2 Nov 2025, Groww autopay video: “Pending SIP payment option not available. Pay option also not available.” https://www.youtube.com/watch?v=tEQVYxdf5JE
- App Store, Paytm Money, 8 May 2025: “There is an issue with the auto debit option.” This is in the set because the file used it as the same failed debit. It is not a Groww comment.

Target segment: a SIP already running on Groww, this month’s debit or bank change broke, and the person wants the month finished.

Value: the person can update the bank or is told not to pay again. The business gets a better chance the SIP is still running a year later. No fee. No claim on ₹46,624 crore.

### Page 5 — problem prioritization

Header: Problem prioritization.

True problem, three why-pills, root cause (86.8% still continuing, 0.9% ended).

Why now: competitive urgency (the complaint is already public on Zerodha Coin, ET Money, Paytm Money, and Groww; Groww’s 17 are not a rate), market momentum, strategic alignment, perfect timing (C3 is 0.5%).

Tree bars and the source bars for the 333, including the Reddit caveat.

Who: Kritika and Madhuri. Value for the business and for the user, as above.

Reach guesstimate: outer ring 10.89 crore accounts, middle ring 10.03 million users, centre about 2.0 lakh, with the 5% and 40% assumptions and ₹40 crore written in the same place.

Impact versus effort:

- Quick win: name the cause, no second payment if the money has left, bank form on the page.
- Major project: a live debit and allotment with the bank and the fund house. Not this demo.
- Maybe: show autopay before a manual payment. Ruchi’s job.
- Don’t bother: return alerts and which fund to buy.

No job-to-be-done bar on this slide.

### Page 6 — MVP scope and feature prioritization

Header: MVP scope and feature prioritization.

Scope: one screen for one monthly SIP when this month did not finish. Demo SIP is ₹2,000, due on the 5th, bank ending 4821, open month November. Confirming does not move money. Nothing is written back to the comment file. In scope is C2. Out of scope: A1, A2, and C1.

Focus: four chips (bank rejected, autopay did not send, money left but not in the SIP, bank change); one next step; helper then a person; no second debit, no fund name, no real payment, no real support agent.

Value: Kritika updates the bank on the page. Madhuri is told not to pay again. Business can count a finished month before three misses. C3 is 4 of 837 (0.5%). No fee. No claim on ₹46,624 crore.

Atomic unit: name the break, take the one safe step, close this month. Amount stays ₹2,000. Next date stays 5 December.

Riskiest hypothesis: people finish the month on the page once the cause is named and the next step cannot charge them twice. Not measured. No survey.

What the demo already runs: each chip is a 3-step path. Bank form takes an optional account-holder name. Bank, account, phone, and address stay ***. The four breaks can change the screen with no model call. A written question uses NVIDIA only, temperature 0, at most two calls. Satisfaction is Yes, or No, connect me with support. History is this visit only. The handoff is a demo ticket that no person receives.

MoSCoW table:

- Must: four named breaks; bank form with other fields masked; no pay button when money has already left; pay this month only (button does not send money); helper on the same page, then support.
- Should: renew UPI autopay from the chat (Ruchi, not a home chip); chat history for this visit.
- Could: live debit and allotment with the bank and the fund house. Not this demo.
- Won’t: return alerts, or which fund to buy.

GTM: on the SIP that already failed, inside the app. Kritika first, Madhuri second. Message is the cause and one safe step, or do not pay again. Learn whether this month finished here, or a second payment was refused. 39.8% is comments. ₹40 crore stays an assumption (5% miss, 40% still open), not a target.

Expectations are a pilot bar, not a result: matching screen, bank form with the account number masked, no pay button when money has left, support only after an answer. The file records that fix 0.5% of the time today.

### Page 7 — solutioning and user flow

Header: Solutioning and user flow.

Left side, four must-haves, each with how it works and impact:

1. Name the break (Decide). Four chips, or one sentence. The match does not call the model. 328 of 333 (98.5%) are an instalment already set up.
2. One safe step (Act). Pay this ₹2,000 only, no pay button if the money has left, bank form with other fields as ***. Kritika and Madhuri.
3. Close this month (Finish). Marked received, bank saved, or wait for units by 7 November on the demo, or the ₹2,000 goes back. Next date stays 5 December. 86.8% still continuing. C3 is 0.5%.
4. Helper, then a person (Ask). “Yes, do it” opens the matching screen. A written question uses NVIDIA, temperature 0, at most two calls. Yes ends it. “No, connect me with support” points to Help in the Groww app. This demo cannot place a call. A note handoff is a demo ticket nobody receives.

Right side is the same four steps as a flow. The fourth column, autopay off, is dashed and marked should-have: the helper can offer it, and it is not a home chip.

Later, not this flow: renew autopay as a home chip (Ruchi), a live debit with the bank and fund house, and return alerts, fund picks, and redemption tracking.

### Page 8 — wireframe ideation

Header: Wireframe ideation.

One image, `slides/wireframe-final.jpg`, shows all five phones. Do not replace it with the Figma embed or with `wireframe-large.png`. The file is 1024×559. It can look soft when the browser enlarges the slide. Leave that until a sharper export exists.

The five notes:

1. Where they start. Pay this instalment opens a check of this month. SIP help is already above Home, Explore, and Portfolio.
2. The one payment. ₹2,000 from the bank ending 4821. Autopay stays off. The button says prototype. No money is sent. The next screen is the failed debit.
3. The debit failed. The app does not yet know why. The person picks bank rejected, autopay missed, or money left. Retry is this ₹2,000 only. Support is on the same screen.
4. Autopay, if they chose it. Autopay missed is the option they tapped. They can turn autopay on for 5 December, or leave it off. Confirming does not move money.
5. Leaving is not success. On Portfolio the ₹2,000 still needs attention. Fund names and ₹1,24,580 are samples, not a fund to buy.

### Page 9 — system design, success metrics, user journey

Header: System design, success metrics, user journey map.

System design, left to right: SIP help screen; screen match with no model call, then NVIDIA at temperature 0 and at most two calls, then mask and decline and a demo ticket; comment file read only (2,480 rows, 837 in-scope, C2 333), this visit’s chat, answer notes; NVIDIA, AMFI, Groww FY26 report. Bank, fund house, and a real support agent are not connected.

Journey, five phases: open the month, name the break, one safe step, close this month, ask then leave. Eight interviews, not a survey.

Measuring success:

- North star: this month finished, or a second payment refused, before the next 5th, and before three misses. Not measured. C3 is 4 of 837 (0.5%).
- Customer lifetime value: not measured. If 5% of 10.03 million miss one month, that is 5.0 lakh. If 40% of those are still open, that is 2.0 lakh. At ₹2,000, about ₹40 crore for one month. Both rates are assumptions. Not a target.
- Activation: matching screen opens. 328 of 333 (98.5%) are an instalment already set up. That is the population, not a measured activation rate.
- Acquisition cost: none claimed. The screen is on a SIP already open.
- Engagement: helper on this page before a person. No time-on-page figure.
- Conversion: name the break, one step, close this month. No percentage. 86.8% of 333 comments say the SIP is still continuing. That is not this rate.
- Revenue: no fee. No claim on ₹46,624 crore.
- Satisfaction: Yes, or No, connect me with support. No score was collected.

Pre-launch guardrails: no pay button when money has already left; no fund and no return; account stays masked; confirming does not move money; the handoff is a demo ticket nobody receives.

Post-launch monitoring: count months finished or second payments refused before the next 5th. No target rate. If people ask for support before the bot answers, review the helper. A second debit on the money-left path stays at zero. Do not read success from the 39.8% comment share, and do not multiply it by 10.03 million.

On the MVP page, one line says where a model is required: the four chips change the screen with no model call. A page with no model would still show those chips. It would not answer a typed question, and it would not decline a fund. A written question uses NVIDIA only, temperature 0, at most two calls. If it is unsure, it says so instead of guessing. The chat was not scored against a golden set. Do not invent that score.

### Page 10 — why it might fail

Header: Risks and mitigations.

Four ways it fails, and the change for each:

- A second debit. Money already left must not still offer pay. Do not ship that button. A second debit on that path stays at zero.
- A mark, not an allotment. The demo is not connected to the bank or the fund house. “Month received” does not mean units were allotted. Say on the screen that confirming does not move money.
- The wrong base. Groww is 17 of the 333 comments. Do not read success from 39.8%, and do not multiply it by 10.03 million.
- They never open it. The old path is a search outside the app. Put the page on the failed instalment. If people ask for support before the helper answers, review the chips.

A reminder, if added later, names ₹2,000, 5 December, and the account ending 4821. It does not read the bank balance, and it does not say pay now when the money has already left. The bank’s own notice, at least 24 hours before a UPI Autopay debit, still has to go out.

## Links already used

- https://www.amfiindia.com/mutual-fund
- https://www.amfiindia.com/uploads/AMFI_Factbook2026_14b34a6447.pdf
- https://resources.groww.in/web-assets/media-library/2026/7/Groww%20Annual%20Report%202025-26.pdf
- https://measure.thisindianlife.today/guides/upi/
- https://ncfe.org.in/wp-content/uploads/2023/12/NCFE-2019_Final_Report.pdf
- https://www.youtube.com/watch?v=YnmMfVU3l94
- https://www.youtube.com/watch?v=tEQVYxdf5JE
- https://www.npci.org.in/uploads/UPI_Consolidated_Circular_0641e910f7.pdf
