V3 CUSTOMER SUPPORT EVALUATION

Measured result:92/100 baseline,94/100 focused,100/100 v3 under the same approved product_issue policy for damaged goods. Historical reviewed results93/100 vs93/100 remain preserved. Six actual prediction fixes, zero regressions.

Start with REPORT.html and the highlighted workbook under outputs/01a1859d-2e04-77e0-b077-31f698f5300d. Inputs, labels, prompt, raw OpenAI responses, comparisons and the executed offline notebook are included. Source artifacts and old LangSmith annotations were not modified.

V3 Exact Match remains100/100. Judge rubric v1 scored99/100; after the user’s separate t033 adjudication and the general billing/refund clarification, rubric v2 scored100/100 on a full100-assessment rerun. Only t033’s score changed; no score regressions. Twelve ambiguity flags remain, all passing. The old automated t033 score0 is preserved; the human score1 and new model score1 are separate records. No independent held-out test has been performed. LangSmith connection is restored, and all100 traces plus100 Exact Match and100 judge feedback records are verified. No GitHub upload was performed for v3.

Offline: run.ps1 -Action analyze; or run build_report.py.
Live missing classifications only: run.ps1 -Action run -DirectNetwork. Accepted saved results are reused without new calls.
Record the completed v3 results to LangSmith when connection is available: run.ps1 -Action publish -DirectNetwork. This performs no OpenAI calls.

Latest judge calibration: llm_judge_v2/before_after.json. Human review: human_reviews/t033.json. Updated rubric: llm_judge_v2/rubric.txt. Workbook tab: Judge v2 review. This is known-example calibration, not independent held-out validation.
