# Groww SIP help — from the comment file to the prototype

Analysis of public comments and five interviews. Not investment advice. The prototype sends no real payment and reaches no real support agent.

The slide file is `slides/deck.html`. Open it in a browser and use the arrow keys. Slide 2 is the problem slide already saved as `slides/01-problem.html`. The comment-engine slide is placed before it, because the problem should be read only after the discovery and the corrections.

The deck now follows the reference PDF: market statistics up front, a research slide with quotes, one primary persona and the others set beside it, a true-problem slide with root cause and value, a high/medium/low priority grid, the wireframe, business/market/operational risk, and a north-star metrics slide. The comment engine still comes before the problem, as requested. Numbers stay sourced. The ₹40 crore line remains an assumption, not a result.

Screens used: `slides/sip-failed-debit.jpg` on the problem slide, and `slides/wireframe.png` on the wireframe slide. Fund names and return figures on the wireframe are illustrative. The prototype does not show them.

---

## 1. How we found it

The engine reads public comments from the Play Store, the App Store, YouTube, and a few lines pasted by hand. It does not store usernames. Reddit was not scraped. Each kept comment is tagged one at a time by NVIDIA Nemotron at temperature 0. The engine was frozen on 2 November 2026.

Counts from `data/evidence_summary.md`:

| Step | Count |
| --- | ---: |
| Raw comments | 54,550 |
| After hygiene | 27,843 |
| After the keyword gate | 5,989 |
| After the relevance check | 3,220 |
| Retagged | 2,477 |
| Confident | 2,284 |
| Needs review | 188 |
| Dropped | 5 |

What it discovered: the largest in-scope pattern is an involuntary stop. The debit failed, the mandate lapsed, the bank changed, or the balance was short. That tag, C2, is 333 comments and ranks ahead of a chosen stop. Only 0.9% of those 333 say the SIP actually ended. Groww is 110 of the 2,477 rows. Groww C2 is 17. Under 30 comments, so this is a pattern, not a Groww rate.

What we corrected: six reviewed rows were all moved to “none”. The model had treated a question, a hypothetical, a wish to start, or a complaint about money that did not come out as if the person’s own SIP had failed or been cancelled.

| Check on the test rows | Before the tighten | After, at temperature 0 |
| --- | --- | --- |
| Stage agreement | 24 of 52 | 44 of 52 |
| Exact tag | 21 of 52 | 40 of 52 |
| “None” | 7 of 35 | 31 of 35 |
| Stage C | 14 of 14 | 10 of 14 |

The last row is the cost of the tighten: some real stage-C comments were missed. The chat evaluation has not been run. Fifteen discovery rows still need labels. Do not quote a model score.

## 2. The problem, the audience, the market

Of people who start a mutual-fund SIP, how many still have one running 12 months later? Two breaks show up, and neither is “they chose to leave.”

- **Involuntary leak.** A debit fails, the mandate expires, the bank changes, or the balance is short. In the tagged comments this is 333 of 837 in-scope rows, 39.8%.
- **Lack of knowledge.** People ask how to start, which step is left, or why a debit failed. Setup comments lead with “how to start a SIP”.

A missed debit becomes a stop because people cannot see why, they leave the app to search, and AMFI, quoting SEBI, treats three missed monthly instalments in a row as a discontinued SIP. NPCI NACH for September 2026 shows 25.2% of recurring debits unpaid (4.9 crore of 19.6 crore). That mix includes EMI, insurance and bills, not SIPs alone, and many are paid on a later try.

Who it is for: a first-time mutual-fund investor on Groww whose SIP should still have one successful instalment in the last 30 days, a year after they started. Groww’s FY26 annual report: 10.03 million mutual-fund active users, SIP inflows of ₹46,624 crore, and over 43% of new SIPs created in India that year. The 333 comments are not 333 Groww customers and not a share of 10.03 million.

Market, September 2026, AMFI: ₹32,490 crore collected, 10.89 crore SIP accounts outstanding, ₹17.86 lakh crore of SIP assets. That month, 63.26 lakh new SIPs and 49.68 lakh discontinued or completed. FY26: 719.22 lakh new against 679.75 lakh discontinued or completed, which includes SIPs that finished their term. The monthly SIP book grew from ₹25,926 crore in March 2025 to ₹32,087 crore in March 2026. The published literacy benchmark remains the NCFE 2019 figure: 27% of Indian adults. No newer NCFE rate is used here.

Where the 837 in-scope comments sit: failed debit 39.8%, chose to stop 29.4%, first debit 15.3%, setup 8.8%.

The path: the instalment is not debited, the person cannot tell why, they look outside the app, and three misses can count as a stop.

## 3. Five interviews

No survey was fielded. These notes are the research. The third conversation is also under the name Akshay and does not give a second age, so it may be the same person or another.

**Hypothesis.** If we name the cause of a missed instalment and offer one safe next step, more of those SIPs will record a successful instalment before the next due date. When the money has already left, that step is an explanation, not a second payment.

**Behaviour.** New investors leave when the first months are hard to read. A debit that vanishes creates a support visit. Some people redeem as soon as they see a gain. Some almost never look, and react only to the moment they happen to open the app.

### Akshay, 22, college student

He started Groww on a friend’s recommendation and a ₹500 SIP. He was enthusiastic, then cancelled after four months because the screen did not show a profit he knew how to read. He had looked on YouTube.

- **Job to be done:** When I am new, help me read the SIP before I decide it has failed me.
- **Pain:** The early months were illegible, so he treated “I cannot read this” as “this is not working.”
- **Aspiration:** An assistant, or a chart that explains itself, so he does not have to leave the app to learn.
- **Quote:** “I could not read the data, so I cancelled.”

### Madhuri, 26, working professional

She wanted a SIP as savings. The amount left her bank and did not show in the NAV. The in-app AI did not help. Support did not satisfy her.

- **Job to be done:** When money leaves my account, show me whether the instalment is still on the way, and bring a person if the explanation is not enough.
- **Pain:** A debit with no visible units, then two dead ends.
- **Aspiration:** A chatbot that tries first, and a direct handoff when it cannot finish the job.
- **Quote:** “The money was cut. It was not in the NAV.”

### Akshay, on redemption

He likes the app. After he redeems, he cannot tell whether the fund house has processed the money, how long the middle steps take, or when it will reach his bank. He moved one or two SIPs elsewhere because of that silence.

- **Job to be done:** When I redeem, show every step from the fund house to my bank.
- **Pain:** The money is in an unnamed gap, so confidence drops.
- **Aspiration:** A status he can check, not a promise about markets.
- **Quote:** “I do not know where the money actually is.”

This job is real and it is not in the current prototype. It is the next journey, after the missed instalment has a measured recovery rate.

### Tarun, 33

He runs many SIPs. When he sees a profit, he stops and redeems, as long as the result is not below what he put in. His goal is a small gain. He also said the charges felt high.

- **Job to be done:** When I book a small gain, show me the cost before I stop.
- **Pain:** He exits on the first visible profit, and the charge is a surprise.
- **Aspiration:** To keep the gain he came for, with the cost written down first.
- **Quote:** “I take the profit out. The charges were high.”

We do not tell him to stay or to leave. A charge explanation can come later. It is not the involuntary leak.

### Rohan

Age was not recorded. He bought a SIP that was in a loss and has not cancelled it. He does not follow the market and does not check often. If he happens to open the app and sees a profit, he is happy. He has not done much research. He would value an update he did not have to hunt for.

- **Job to be done:** When I rarely open the app, tell me the status in one plain line.
- **Pain:** He is invested and uninformed, so his mood depends on a random glance.
- **Aspiration:** To stay invested without becoming a researcher.
- **Quote:** “I have not researched it. I look when I happen to open the phone.”

A notification of returns would become advice. It is out of this prototype.

### What the interviews change

The missed-debit and “money left but not showing” stories match the comment engine. The knowledge gap matches the setup comments. Redemption tracking, profit alerts, and charge disputes are neighbouring jobs. They are written down so we do not pretend the chatbot will do them.

## 4. The true problem

**Frame.** A SIP dies in the gap between a debit the bank did not complete and a screen the person cannot interpret. The job is to close that gap before three misses are treated as a stop.

**How we know.** It survived the correction pass and is still the largest in-scope tag. The three-miss rule makes the cost concrete. Two interviews describe it in a life, not in a tag. We still do not know the Groww rate.

**Why now.** Discontinuations or completions in FY26 sit close to new SIPs. Groww opens a large share of those new SIPs. Recurring debits already fail often in the wider NACH data. Waiting for a perfect public SIP-only rate delays a screen we can test internally.

**Who.** First, the new mutual-fund SIP investor with a small instalment and a new vocabulary. Beside them, the saver whose debit and NAV do not match, and the person whose bank changed before the debit day.

**Value.** One month completed, or a clear instruction not to pay again. A better chance the SIP is still running at month 12. Trust at the moment people currently leave. No fee for the repair, and no claim on returns.

The sentence to keep: help the person finish this month’s instalment, or show them that the money has already left. Do not advise them to start, stop, or switch a fund.

## 5. What we build first

| Job | Why this order | In the prototype |
| --- | --- | --- |
| Pay this instalment only | Recovers the month without changing the SIP | Yes |
| Money already left | Stops a second debit | Yes, and there is no pay button |
| Autopay off or not sent | The debit never starts | Yes |
| Bank change | The old account cannot send it | Yes |
| Redemption tracker | Real, and a different journey | No |
| Return or stock updates | Asked for, and it becomes advice | Refused |

The prototype uses one sample SIP: ₹2,000 due on the 5th, from the bank account ending 4821. The next date stays 5 December. There are four causes, at most three short steps, and one green action. The chat opens with “Hi, what can I help you with?” It can answer why a payment failed, fill the matching screen, and ask whether the person is satisfied. If not, it offers a call from Help in the Groww app. The demo cannot place the call. On a bank change, only the account-holder name can be typed, and it can be left blank. The bank name, account number, phone and address are filled as `***`. Send sits under those fields.

**Guestimate, labeled as assumptions.** Do not multiply 39.8% of comments by 10.03 million users. If 5% of those users miss one instalment in a year, and if 40% of those misses are still unrecovered at the next due date, that is about 2.0 lakh instalments. At ₹2,000, that is about ₹40 crore of a single month not completed. Both percentages sit below the 25.2% NACH unpaid figure on purpose, because that figure is not SIPs alone. Replace them with the internal rate before the ₹40 crore line is used outside this working note. It is not Groww’s loss and not a target.

**Impact against effort.** High impact and lower effort: the “money already left” status, and a plain answer to “why did it fail?” High impact and higher effort: pay-this-month, autopay renew, and, later, a redemption tracker. Lower impact on this leak: the masked bank-change form. Not this release: profit alerts, chart tutoring, charge disputes.

## 6. The flow

Failed debit, or the SIP help tab → what happened → three calm steps → one confirmation → received, or autopay on, or bank details sent as `***`, or “do not pay again” → “Are you satisfied?” → yes, or a call.

Closing help does not mark the payment done. Going back to the portfolio does not complete it either. Chat history shows the whole exchange for the visit and clears on a full refresh.

A wrong tap must not start a second payment, change the amount, move the next date, recommend a fund, show a return, or invent a support number.

## 7. Wireframes — decide, plan, commit, reflect

The five phones in `slides/wireframe.png`:

1. **Decide.** SIP overview. Pay this instalment is the entry. SIP help stays in the bar.
2. **Decide.** Review ₹2,000 for this month only. Autopay is unchanged unless they confirm a change. The pay control is marked as a prototype.
3. **Plan.** Payment failed. The reason is not confirmed. Retry ₹2,000, or open SIP help.
4. **Commit.** They choose what happened, read the step, and turn autopay on or retry. One explicit review.
5. **Reflect.** Portfolio. SIP help is still there. Illustrative holdings are not the product.

## 8. System, journey, north star

The screen is a state machine. It does not call a model. The chat masks personal numbers, refuses advice, refuses news, returns and fund names, and makes at most two NVIDIA calls. Below 0.6 confidence it says it will not guess. Replies follow the language of the message. The conversation stays in the browser session.

| Moment | What they feel | What the product does |
| --- | --- | --- |
| Debit day | Unsure | The instalment is still due |
| Failure | About to search | SIP help opens on the cause |
| Choice | Four plain labels | A three-step plan |
| Commit | One tap | This month only, or no second pay |
| Doubt | Still stuck | Chat, then a call if unsatisfied |

**North star.** The share of failed instalments recovered before the next due date. It measures the missed month, not comments and not a return. If the money has already left, recovery means the person is told not to pay again, and does not.

| Lens | Count | Do not |
| --- | --- | --- |
| Activation | Opened SIP help from a failed debit | Scare lines, countdowns, “last chance” |
| Engagement | Finished the steps, or marked the answer helpful | A guess when the model is unsure |
| Conversion | Month received, autopay on, or bank form sent | A second debit after the money has left |
| Revenue | Nothing on this screen | A fee to repair the explanation |
| Satisfaction | “Are you satisfied?” and the call after a no | A made-up support phone number |

## 9. Money, distribution, risk

The screen should not charge for the repair. The value is a SIP that keeps running. Groww’s FY26 SIP inflows of ₹46,624 crore are context, not a number this screen can claim. A recovered ₹2,000 instalment is retained contribution. Any support saving is unmeasured.

Distribution: the failed-payment screen, beside retry; SIP help in the bottom bar; the chat for “why did this fail?” Not a new app, not an ad, and not an email that urges a larger investment.

| Risk | Response |
| --- | --- |
| Business: a second pay after the money has left | That path has no pay button |
| Market: the screen can be copied | Show it on our own failed debit, with our own next date |
| Operations: a guessing bot increases support | Under 0.6 confidence, refuse, then offer a call. The support URL is still to be verified |
| Comment share is read as a customer rate | Say 333 comments, and 17 on Groww, every time |
| The screen gives advice | Block news, returns, fund names, and “should I stop” |
| A phone or account number is typed | Mask it. Bank fields other than the name are `***` |
| Wireframe returns are taken as the product | Those figures are illustrative and are not in the prototype |
| We ship before the chat is scored | Fifteen rows still need labels |

**Decision this deck asks for.** Measure the internal unrecovered-instalment rate. Keep this scope. Replace the assumption guestimate only after that rate exists. Do not add returns, fund picks, or a redemption tracker to this release.

## What was added beyond the outline

- The engine and its corrections are a full slide, placed before the problem.
- The five interviews are written as job, pain, aspiration and quote. Neighbouring jobs are kept visible and marked out of scope.
- The guestimate is shown with both assumptions in the same paragraph, so ₹40 crore cannot travel alone.
- The wireframe is included, with a line that its fund names and returns are not the prototype.
