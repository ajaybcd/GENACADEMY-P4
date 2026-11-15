# LLM judge add-on report

All 200 saved predictions received validated judge assessments under one frozen routing rubric. The judge passed 92/100 baseline and 93/100 focused predictions, an observed difference of +1 percentage point **under that rubric**. An identical-input inconsistency on t033 makes this difference unreliable as evidence of classifier improvement. The authoritative reviewed-label Exact Match result remains 93/100 versus 93/100. Judge feedback does not replace it or establish that the reviewed labels are wrong.

| Measure | Baseline | Focused |
|---|---:|---:|
| Original-label Exact Match | 92/100 | 94/100 |
| Reviewed-label Exact Match | 93/100 | 93/100 |
| LLM rubric passes | 92/100 | 93/100 |
| Ambiguity flags | 10/100 | 12/100 |
| Score agrees with original-label EM | 100/100 | 99/100 |
| Score agrees with reviewed-label EM | 99/100 | 98/100 |

## What was evaluated

The inputs are the fresh saved baseline and focused LangSmith prediction exports, each covering the same 100 synthetic tickets from 25 seed families with paraphrases. No classifier was rerun. The original labels yield 92/100 versus 94/100. Applying the participant's t046 correction equally to both predictions yields 93/100 versus 93/100, seven wins, seven regressions and 86 unchanged passes. The older Evaluation tab's 92% to 97% belongs to a separate broader repository revision. Prior approved failure cases remain 11/11 older and 14/14 fresh; approval records review completion, not objective correctness.

## Method and pilot

Judge model: `gpt-5.4-mini-2026-03-17`; low reasoning, maximum 2048 completion tokens, provider-default temperature, no tools, store false. The snapshot was confirmed available through authenticated model listing. It was chosen for structured task fit and modest cost, not demonstrated superiority. Settings, exact rubric and schema are saved separately. [Official model guidance and rates](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices) informed the implementation.

Requests contain only the frozen rubric and ticket query plus prediction, without labels, approvals, version names, existing scores, experiment names or notes. Baseline and focused use identical criteria and a fixed shuffled order. The 16-assessment pilot spans eight tickets and all five categories. The implementing AI inspected the accepted rationales before the full run; this is not independent human calibration. Pilot judgments are included once in the 200. No model or rubric changes were made after the pilot. Invalid/inconsistent output is rejected, retained and retried using identical inputs.

The policy prioritizes non-delivery over a refund remedy (order_status), delivered-product defects over a refund remedy (product_issue), and routes missing refund payments after returns and unwanted-order cancellation with refund to refund_request. Account problems must be actual access, detail-change or checkout failures; general discounts/sales are other. Ambiguity flags surface credible alternate routing choices without automatically awarding a pass. The precedence policy is an explicit choice informed by existing notes; it overlaps the focused classifier prompt and is not an independent validation of that policy. Full details are in [METHOD.md](METHOD.md) and [rubric.txt](rubric.txt).

## Paired findings and review

Judge paired changes: {"UNCHANGED_PASS": 85, "WIN": 8, "REGRESSION": 7}. Proposed-intent inconsistencies across versions: ['t033']. Ambiguity-flag inconsistencies: ['t033', 't056', 't057', 't059']. These limited checks do not establish repeatability or independence from the presented prediction. Among 24 parsed rejected responses, retrying changed 0 scores and 0 proposed intents relative to accepted judgments; details remain in summary.json.

Tickets flagged for participant review: t004, t005, t006, t007, t033, t044, t045, t046, t047, t056, t057, t058, t059. [review_needed.csv](results/review_needed.csv) contains every flagged assessment, its rationale, alternatives and both labels. [disagreements.csv](results/disagreements.csv) separates disagreements with original and reviewed references. A flag is not an approval or automatic label change.

The t046 damaged-laptop refund case is the key policy disagreement: the participant selected refund_request, while the frozen underlying-problem rule proposes product_issue. Both positions remain visible. The judge evaluates a declared rule, so any resulting advantage for focused predictions is conditional on that rule, not evidence that the participant's policy preference is invalid.

The t033 overcharge case is a judge inconsistency: both classifiers predict refund_request and both judge requests are identical. One judge response accepts the refund routing; the other calls it account_help because it interprets the overcharge as a checkout failure. This is not a classifier regression. Across 86 identical-input pairs, it is the only score disagreement. Changed predictions contribute +2 judge passes; identical-input variation contributes -1. Preserve both judgments and ask the participant to adjudicate the boundary; do not rerun until the scores agree.

**t004 baseline** — prediction `refund_request`, judge 0, proposed `order_status`, ambiguity True. The customer states non-delivery as the underlying issue (“I never received my order”), which the policy routes to order_status before the requested refund remedy.

**t004 focused** — prediction `order_status`, judge 1, proposed `order_status`, ambiguity True. The customer states they never received the order, which is a non-delivery issue routed to order_status, and the money-back request is secondary under the precedence rule.

**t024 focused** — prediction `order_status`, judge 0, proposed `refund_request`, ambiguity False. The customer is asking about a missing refund after returning the item, which falls under refund_request rather than order_status because it concerns refund payment status, not delivery progress.

**t028 focused** — prediction `order_status`, judge 0, proposed `refund_request`, ambiguity False. The customer is asking to cancel an unwanted order and refund the card, which the policy routes to refund_request rather than order_status.

**t046 baseline** — prediction `refund_request`, judge 0, proposed `product_issue`, ambiguity True. The query states the laptop arrived damaged, which is a product issue; the requested full refund is secondary and should not override the underlying defect under the routing precedence rules.

**t046 focused** — prediction `product_issue`, judge 1, proposed `product_issue`, ambiguity True. The customer says the laptop arrived damaged, which is a delivered-product defect, and the refund request is only the remedy, so the best intent is product_issue under the precedence rule.

## Usage, preservation and limitations

There were 254 recorded API attempts, including 54 rejected/failed attempts. Returned usage totals 152,206 prompt tokens (0 cached) and 24,222 completion tokens including reasoning. Estimated returned-usage cost is **$0.2232**, calculated from published rates rather than an invoice. Attempts without returned usage may have unknown billing. The initial run was interrupted to shorten stalled transport calls from 120 to 30 seconds; at most 4 additional in-flight requests lack usage records. This changed no rubric or model setting. Raw recorded attempts and failure types are retained; no unresolved final assessments remain when validation passes.

The source-project hash inventory confirms preservation of its existing artifacts. No LangSmith writes were performed: its 8/8 baseline and 7/7 focused completed queues, 15 run reviews for 14 tickets and 75 verified feedback records remain as before. No existing predictions, labels, Excel approvals, annotations, report or notebook were changed. Existing evaluation had no LLM judge; this folder is the separate add-on.

This is descriptive reuse of synthetic paraphrases, not independent held-out validation. A single judge can share model-family biases, anchor on candidate predictions, misinterpret policy or vary across calls; retries select internally valid output and do not guarantee semantic accuracy. Ambiguity estimates are advisory. Independent human adjudication of flagged cases and a future held-out family sample are needed before automated approval. No statistical significance, production benefit or unconditional improvement is claimed.

**Interpretation:** the judge adds a policy-specific view and exposes where the label correction and underlying-problem rubric differ. It does not change the original final conclusion of no net improvement under the participant-reviewed labels.
