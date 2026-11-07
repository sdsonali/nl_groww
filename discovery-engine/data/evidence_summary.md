# Evidence log

Numbers below are copied from the file named in the same sentence. This note does not add a best-problem label and it does not recommend a change.

## a. Sources and funnel

From `data/funnel.json`:

| Step | Count |
| --- | ---: |
| Raw total | 54,550 |
| Play Store | 45,645 |
| YouTube | 5,905 |
| App Store | 2,990 |
| Manual | 10 |
| After hygiene | 27,843 |
| After the keyword gate | 5,989 |
| After the relevance check | 3,220 |
| Tagged | 2,477 |
| Confident on that older tag | 2,297 |
| Needs review on that older tag | 180 |

`data/funnel.json` also records the model as `nvidia:nvidia/nemotron-3.5-super-vl-120b-a12b` and 1,374 API calls. The collected-at time in that file is 2026-10-25T15:25:07Z.

From `data/final_retag.csv` (the retag, not the older tag):

| Step | Count |
| --- | ---: |
| Retagged rows | 2,477 |
| Confident (`status` ok, and the scorer keeps them) | 2,284 |
| Needs review | 188 |
| Dropped | 5 |

`data/final.csv` and `data/final_v1_old_prompt.csv` also have 2,477 rows. Those two files are the older tags. They were not mixed into this score.

`data/changes_log.csv` records the finish line: started from 1,648 previously saved rows, 829 new rows this run, file now 2,477.

## b. Golden set

`data/audit_answers.csv` has 105 comments, 15 in each of 7 groups: Cancelled, no reason given; Support did not resolve it; Money was hard to withdraw, or redemption was slow; C2; A1; C1; none.

Labels were drafted with Claude's help, then reviewed row by row and accepted by the PM.

## c. Agreement results

The first comparison is stored in `data/audit_sample.csv`: `human_correct (yes/no)` is yes on 47 of 105 rows and no on 58 of 105. That column was filled from stage agreement.

The later tune and test numbers are in `data/changes_log.csv`. Odd rows were the tune set (53). Even rows were the test set (52).

Old prompt, before the tighten:

| Set | Stage | Exact node | none | Stage C |
| --- | --- | --- | --- | --- |
| Tune | 23 of 53 | 19 of 53 | 8 of 35 | 12 of 13 |
| Test | 24 of 52 | 21 of 52 | 7 of 35 | 14 of 14 |

New prompt at temperature 0.1:

| Set | Stage | Exact node | none | Stage C |
| --- | --- | --- | --- | --- |
| Tune | 40 of 53 | 38 of 53 | 28 of 35 | 9 of 13 |
| Test | 40 of 52 | 37 of 52 | 28 of 35 | 10 of 14 |

A second view of that same temperature-0.1 run, called the pipeline view in the log: tune stage 43 of 53, exact 41 of 53, none 31 of 35, stage C 9 of 13. Test stage 41 of 52, exact 38 of 52, none 31 of 35, stage C 8 of 14.

Temperature-0 rerun of the same prompt, saved in `data/audit_retag.csv`:

| Set | Stage | Exact node | none | Stage C |
| --- | --- | --- | --- | --- |
| Tune | 40 of 53 | 37 of 53 | 30 of 35 | 7 of 13 |
| Test | 44 of 52 | 40 of 52 | 31 of 35 | 10 of 14 |

Where the temperature-0.1 run and the temperature-0 run differ, the range is:

| Check | Range |
| --- | --- |
| Tune exact | 37 to 38 of 53 |
| Tune none | 28 to 30 of 35 |
| Tune stage C | 7 to 9 of 13 |
| Test stage | 40 to 44 of 52 |
| Test exact | 37 to 40 of 52 |
| Test none | 28 to 31 of 35 |
| Test stage C | 10 of 14 on both runs |

`data/audit_retag_v2.csv` is post-hoc, not an independent test. Agreement was not scored. The log records tree counts A1 4, A2 4, B1 0, B2 0, C1 24, C2 13, C3 0, D1 1, E1 1, none 58. Scope: in_scope 51, exit_experience 12, other_platform_complaint 19, unclear 23. Both new fields were filled on 105 of 105 rows.

## d. Where the engine failed

In plain words, from the corrections and the agreement log:

- Questions and hypotheticals were tagged as if something had happened to the commenter's own SIP.
- Exit complaints, including money that did not come out after a cancel, were tagged C1.
- A wish to start a SIP, with no setup and no first debit, was tagged A1.
- The tightened rule then missed some real stage-C comments. On the test set, stage C agreement went from 14 of 14 before the change to 10 of 14 after it, and stayed 10 of 14 on the temperature-0 rerun. On the tune set it went from 12 of 13 to 9 of 13, then to 7 of 13 at temperature 0. That is the stage C recall cost.
- Tried-to-cancel rows and recurring instalment problems were the misses the later prompt rule was written to catch. The full 2,477 were retagged after that rule. The 105-row file `data/audit_retag_v2.csv` is post-hoc, not an independent test, so it does not measure whether those misses are gone.

## e. Corrections

These are the six rows in `data/corrections.csv`. The human correction on each one is `none`.

| Row id | What the model had said | Why it was changed |
| --- | --- | --- |
| c14a8ecb1b936793 | C1 (voluntary stop) | A question about what stopping does. The person does not say they stopped their own SIP. |
| 6feffe55f757a840 | C1 (voluntary stop) | Money not received after cancelling. An exit complaint, not a reason for stopping. |
| c13dab6df110845b | A1 (SIP started) | The person only wants to start a SIP. No setup and no first debit. |
| 45b1fe45394de990 | C2 (involuntary failure) | A hypothetical question. The person does not say a debit failed for them. |
| a3638311e3c8772c | A1 (SIP started) | The person has not started a SIP. An affordability worry, not an A1 event. |
| 9a69e4d9fdeff67f | C1 (voluntary stop) | Cancelled, and the money was not withdrawn. The complaint is about getting money out. |

## f. Changes

Short table from `data/changes_log.csv`. Progress lines for every 200 new rows are in that file and are not repeated here.

| Change | Before | After |
| --- | --- | --- |
| Added metric_scope | Confident 2,297. Top C2 n=369 score 1.3727 | Confident 1,569. Top C2 n=297 score 1.631 |
| Questions tab, one reason each | Overlapping keyword counts on 374 comments | Same 374, each counted once |
| Loosened hard-to-withdraw | Hard to withdraw 7 of 374 | Hard to withdraw 20 of 374. Cancelled, no reason given 109 |
| Recurring instalment check, older tags | C2 n=297 score 1.631 | C2 n=276 score 1.5465. On that older file, in-scope confident C2 was yes 229, no 21, unclear 47 |
| Tightened prompt | Test stage 24 of 52. Test stage C 14 of 14 | Test stage 40 of 52. Test stage C 10 of 14 |
| Temperature 0 rerun | Test stage 40 of 52. Test exact 37 of 52 | Test stage 44 of 52. Test exact 40 of 52 |
| Post-hoc 105 | Not scored | post-hoc, not an independent test |
| Format choice | 5 per batch returned 4 of 20 | 1 per call returned 20 of 20. That format was used |
| First retag stop | Started from 38 rows | File then 1,583 rows |
| Score on those 1,583 | Older file not used | Confident 1,522. Top none, then C2, then C1 |
| Retag finished | Started from 1,648 rows | File now 2,477 rows. New this run 829 |
| Score on all 2,477 | Older file not used | Confident 2,284. none 1,453 score 0.6405. C2 333 score 0.4453. C1 249 score 0.4168 |

## g. Honest limits

- Public comments over-represent angry and happy users.
- First-12-month investors are under-represented.
- Only 110 of the 2,477 retagged rows are Groww (`data/final_retag.csv`).
- Competitor rows and YouTube rows are a comparison set.
- The audit sample was drawn from the engine's own themes, so it measures positive-tag precision, not recall on missed events.
- Run-to-run variation is the range in section c.
- Some Play Store collection uses an unofficial library (`google-play-scraper` in `1_collect.py`).
- Reddit was not scraped. `data/funnel.json` lists 4 manual rows under `manual|Reddit`. Those are pasted lines, not a Reddit collection.
- Groww node counts in the score are under 30 (C1 is 12, C2 is 17). The page says "Too few comments to rely on" for a count under 30.
- 38 retagged rows have an empty `tenure_hint`. They are the rows kept from before the compact prompt.

## h. Privacy

Public text only. `data/final_retag.csv` has no username, author, profile, email, or handle column. A scan of the comment text found 0 email addresses and 0 @handles.
