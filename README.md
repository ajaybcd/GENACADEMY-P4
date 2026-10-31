# GENACADEMY P4

Week 4 customer support intent evaluation using OpenAI and LangSmith.

## Final submission

- [Final report](outputs/project_report.html) — download and open in a browser.
- [Executed analysis notebook](customer_support_evaluation.ipynb)
- [Approved evaluation workbook](outputs/customer_support_evaluation.xlsx)
- [LangSmith annotation completion evidence](outputs/langsmith_annotation_sync/completion_notes.txt)
- [Walkthrough script](walkthrough_script.txt)

| Scoring view | Baseline | Focused | Wins | Regressions |
| --- | ---: | ---: | ---: | ---: |
| Original LangSmith labels | 92/100 | 94/100 | 8 | 6 |
| Participant-reviewed labels | 93/100 | 93/100 | 7 | 7 |

All failed-case reviews are approved: 11/11 saved-run cases and 14/14 fresh cases. The LangSmith queues have 8/8 baseline and 7/7 focused run reviews completed, with 75 feedback records verified. One reviewed reference label changed; original model predictions were preserved. The final reviewed comparison shows no net accuracy gain.

**Remaining participant step:** record the Loom walkthrough and submit its actual link. The optional LLM judge was not attempted.

Run `python verify_submission.py` to re-execute the 10 analysis cells and check the final evidence without API calls. The OpenAI/LangSmith SDK is required only for new live runs or annotation transfers. Saved credentials and local environments are excluded from this repository.


This project implements the supplied **Evaluations Using LangSmith** handout using its linked customer-support repository. The initially supplied 4B social-media repository remains in `../repository` as reference. It is a different assignment.

## Current evidence

The 100 fixed tickets and two prediction exports come from `The-Gen-Academy/4A-Customer-Support-Agent-Evaluation`, commit `ef517b274cf86a2c4fa8ae72fdc89b3dce80f41d`. Saved predictions reproduce **92/100 baseline** and **97/100 upstream revised**, with **8 wins and 3 regressions**. These are repository results, not new model calls or new LangSmith experiments. The upstream revision changes multiple instructions and therefore does not establish the effect of our one focused change.

Fresh LangSmith runs completed on the same 100 tickets with no API errors. Under their original labels, results are **92/100 baseline → 94/100 focused**, with **8 wins and 6 regressions**. After the participant changed t046 from product_issue to refund_request on Fresh evaluation, both unchanged predictions rescore to **93/100**, with **7 wins, 7 regressions, 86 unchanged passes and no unchanged failures**. The focused change provides no net gain under the final reviewed labels. Original cloud labels and evaluator scores are retained; reviewed labels and scores are separate feedback fields.

[Open the actual LangSmith comparison](https://smith.langchain.com/o/b21f8ce6-e07f-4579-b2f2-b4ca372647f3/datasets/b97bfa75-95ea-4c09-b9b9-cbb8493da698/compare?selectedSessions=b2f408bc-391e-49a4-bb96-58ba78619308%2Cf1866797-b7bb-48c1-963a-2b154308d4fd).

Failure reviews are complete: **11/11 saved-run cases and 14/14 fresh cases approved**. The LangSmith queues are complete: **8/8 baseline and 7/7 focused items**, covering 14 distinct tickets, with **75 feedback records read back**. The project includes the final report, executed notebook, workbook, reviewed CSV exports, prompts, retained predictions, queue evidence and screenshots. The remaining participant action is recording the Loom walkthrough and supplying its actual link. The optional LLM judge was not attempted.

## Run locally

Python 3.10 or later is sufficient for offline analysis and the direct OpenAI runner.

```powershell
python build_deliverables.py
python verify_submission.py
```

Open `outputs/project_report.html`, `outputs/customer_support_evaluation.xlsx`, and `customer_support_evaluation.ipynb`. The finalizer reads the approved workbook and retained evidence, executes local analysis, and updates the report, notebook and final CSV/JSON snapshots. It makes no API calls and does not rewrite the workbook. The original workbook builder creates initial drafts and is not part of finalization. Original run exports remain untouched. Future label changes require another evidence reconciliation before submitting.

## Fresh runs

For reusable Windows account-encrypted storage, run `powershell -NoProfile -STA -File .\credentials.ps1 -Action Configure`. Enter both keys in the masked local window. The encrypted `.credentials.local.json` is ignored by Git and can be decrypted only by this Windows account on this machine. Check it with `-Action Check`. Use `-Action RunBaseline`, `-Action RunFocused`, or `-Action RunLangSmith -DatasetName YOUR-UNIQUE-NAME` to load saved credentials for a run. The wrapper removes the keys from its process environment afterward. Install the LangSmith requirements before RunLangSmith. To replace keys, run Configure again.

Set credentials locally in your shell or credential manager. Do not put keys in chat, the workbook, or source control. `.env.example` documents names; Python does not automatically load `.env`.

```powershell
python project.py live --version baseline --output live_runs/baseline.csv
python project.py live --version focused --output live_runs/focused.csv
python project.py compare --baseline live_runs/baseline.csv --focused live_runs/focused.csv
```

Each command evaluates all 100 tickets using gpt-4o-mini at temperature 0. Output is exactly `{"intent": "..."}` under a strict enum schema. The classifier receives only the prompt and query. Ground truth enters Exact Match afterward. Errors stay unscored and are counted separately. Output files are created exclusively to preserve previous runs. API calls incur model charges; Exact Match itself does not use tokens.

## LangSmith experiments

Install `requirements.txt` in your own virtual environment, set `OPENAI_API_KEY` and `LANGSMITH_API_KEY`, then run:

```powershell
python project.py langsmith --dataset week4-p4-your-unique-dataset-name --prefix week4-p4
```

This creates a new dataset and two fresh experiments, with local prediction and experiment metadata exports in `live_runs`. A duplicate dataset name should be treated as an error; use a new name to preserve prior evidence. Use the actual experiment links printed by LangSmith. The SDK path is optional: the UI path below follows the handout directly.

1. Upload `outputs/langsmith_dataset.csv` with **query → Input**, **intent → Output**, **id → Metadata**. Exactly these three columns are included.
2. Paste `prompts/baseline.txt` as System and `{query}` as Human. Map `{query}` to `input.query`. Select f-string formatting.
3. Configure required String property `intent` in the output schema, model `gpt-4o-mini`, temperature `0`.
4. Add only code-based Exact Match on `output.intent` versus `referenceOutput.intent`. Run all 100 rows under a unique baseline experiment name.
5. Filter score 0 and send every failure to an annotation queue. Write a note for every failure before defining categories. The supplied notes are AI-assisted drafts, not participant-completed annotations. If fresh failures differ, derive categories from the fresh notes.
6. Add required categorical feedback `failure_category` using the categories actually discovered. Complete participant review.
7. Replace only the System prompt with `prompts/focused.txt`. Keep dataset, labels, schema, model, temperature, and evaluator unchanged. Run all 100 rows under a new experiment name.
8. Select both experiments in Comparison. Record total/completed/error counts, accuracy delta, wins, regressions, unchanged passes, and unchanged failures. Inspect t016, t094, and t095 explicitly.
9. Save actual dataset and comparison URLs plus screenshots of column mapping, baseline summary, all failure annotations, prompt change, improved summary, and regressions. No links or screenshots have been fabricated.

## Routing policy and label review

The LangSmith annotation queue transfer is complete. `Week4 P4 baseline approved Excel reviews` has 8/8 completed items, and `Week4 P4 focused approved Excel reviews` has 7/7, with no pending reviews. These are imports of the participant-approved workbook reviews, recorded as API feedback with provenance. The 15 run records cover 14 unique tickets because t046 has a reference-label correction. The older Evaluation tab has no matching live run IDs and was not imported. See `outputs/langsmith_annotation_sync/completion_notes.txt` and `sync_evidence.json`. No model calls were made during the transfer. Original experiment labels and scores remain intact; reviewed labels and scores are separate feedback keys.

The supplied seed policy prioritizes the underlying problem: non-delivery with a refund request stays `order_status`; a damaged item with a refund request stays `product_issue`. This is a business routing choice, not the only reasonable interpretation of customer intent. The baseline prompt under-specifies that precedence. Retain the policy for this comparison; have the participant approve it. If labels change, rescore **both** saved versions under the same reviewed labels and create a new dataset snapshot for fresh runs. Never relabel simply to agree with a model.

The 100 tickets are 25 seed families with three paraphrases each, so apparent gains are correlated and do not establish performance on unseen ticket families. Evaluate a held-out set before making a broader reliability claim.

## Deliverables and outstanding actions

| Requirement | Artifact or action |
| --- | --- |
| Dataset | `outputs/langsmith_dataset.csv`, 100 rows, exact required columns |
| Spreadsheet | `outputs/customer_support_evaluation.xlsx`; all failed-case participant approvals completed |
| Notebook | `customer_support_evaluation.ipynb`; all analysis cells executed locally, no network or model calls |
| Notes before taxonomy | `outputs/failure_notes_before_categories.csv` |
| Taxonomy | `outputs/failure_categories.csv`, one baseline mechanism plus one observed upstream regression mechanism |
| Prompt fix | `prompts/baseline.txt` and `prompts/focused.txt`, one added paragraph |
| Saved regression evidence | `outputs/regression_results.csv`: all eight original failures, three upstream regressions, one previously passing control |
| Fresh regression evidence | `outputs/fresh_regression_results.csv`, 14 affected tickets plus passing control; all 100 predictions retained in `live_runs` |
| LangSmith evidence | Completed; actual dataset, experiment identifiers and comparison URLs in `live_runs/langsmith_evidence.json` |
| Loom | `walkthrough_script.txt`; participant records and submits |

## Technical references

- [Source repository](https://github.com/The-Gen-Academy/4A-Customer-Support-Agent-Evaluation)
- [LangSmith evaluation quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)

The source notebook and exports are retained in `source/`; the SHA-256 manifest records their local contents. The original notebook demonstrates broader revisions and OpenTelemetry tracing. This implementation uses LangSmith experiments directly and avoids adding reference labels to classifier inputs.
