# Customer Support Intent Evaluation Using LangSmith

Final v3 submission for Week 4 Project 4 by Ajay David, updated November 14, 2026 (US Eastern).

## Final measured results

| Measure | Before | Final |
|---|---:|---:|
| Classifier Exact Match, same approved policy | Focused 94/100 | V3 100/100 |
| LLM judge on the same v3 outputs | Rubric v1 99/100 | Rubric v2 100/100 |

The saved baseline scores 92/100 under that same final policy. V3 corrected six focused-model predictions, t024–t029, with zero regressions. Historical reviewed 93/100 versus 93/100 scores remain preserved; they used refund_request for damaged ticket t046. The participant now approved product_issue for that damaged-product case. Therefore the old 93% to final 100% difference includes one label-policy point and six prediction fixes.

These scores apply to the **known 100 synthetic tickets**, derived from 25 seed scenarios with three paraphrases each. There is no independent held-out test, and historical controls were rescored rather than rerun concurrently. Judge v2 was calibrated on the known t033 disagreement; it is not proof of general judge reliability. Twelve ambiguity flags remain, all passing; flags are not automatic human approvals.

## Submission files

- [Final report](outputs/project_report.html) — download the repository and open this HTML file in a browser.
- [Executed project notebook](customer_support_evaluation.ipynb)
- [Word narration, 90-second demo and 20-point summary](outputs/project_transcript_and_summary.docx)
- [20-line summary](outputs/project_summary_20_lines.txt)
- [PowerPoint with speaker notes](outputs/customer_support_project_presentation.pptx)
- [Highlighted v3 comparison and judge workbook](v3/outputs/01a1859d-2e04-77e0-b077-31f698f5300d/v3_evaluation_review.xlsx)
- [Preserved historical review workbook](outputs/customer_support_evaluation.xlsx)
- [V3 and judge report](v3/REPORT.html), [executed v3 notebook](v3/v3_analysis.ipynb)
- [Classifier comparison](v3/results/comparison.json), [judge before/after](v3/llm_judge_v2/before_after.json)
- [Separate human t033 adjudication](v3/human_reviews/t033.json)
- [Verified LangSmith evidence](v3/results/langsmith_v3_evidence.json)
- [Original completed judge add-on](llm-judge/REPORT.md) — historical baseline/focused analysis.

The existing [November 1 video walkthrough](outputs/2026-11-01%2021-08-52.mp4) predates v3. Use the updated transcript and demo script to record a walkthrough of the final results. The existing video and prior commits are preserved.

## Final voice-over audio

These tracks use an **AI-generated Cedar voice**. The narration covers final v3 classifier 100/100 and calibrated judge 100/100, with the historical results and limitations retained.

- [Presentation narration — 3 minutes 57 seconds](outputs/voiceover/final_v3_presentation_voiceover.wav)
- [Demo narration — exactly 90 seconds](outputs/voiceover/final_v3_demo_90_seconds.wav)
- [Slide and screen-change cues](outputs/voiceover/recording_cues.csv)
- [Recording instructions and disclosure](outputs/voiceover/README.txt)

Download the WAV files to play them or import them into your video editor. Enable system-audio recording when playing them during a screen recording. Add the caption: “AI-generated voice-over; project review and approvals by Ajay David.”

## What changed

GPT-4o-mini predicts one of order_status, refund_request, product_issue, account_help or other. V3 retains actual non-delivery as order_status and damaged products as product_issue, but explicitly routes missing refund money after a return and unwanted-order cancellation refunds to refund_request. Prompts, inputs, responses, settings and scoring evidence are saved under v3.

GPT-5.4-mini-2026-03-17 separately judged saved query/prediction pairs without reference labels or human approval inputs. Rubric v1 rejected t033, an overcharge reimbursement request. The participant separately approved refund_request; rubric v2 generally clarifies billing refunds versus technical checkout failures. All 100 outputs were judged again using the same model, schema and settings. Only t033 changed score, from 0 to 1. Its old automated 0, human 1 and new automated 1 remain separate. All 100 final judgments validated after 114 attempts, including 14 failed/rejected attempts.

## Human review and LangSmith

The participant added and confirmed Excel notes in column L and approved reviews in M. The original Evaluation tab retains 11/11 approved failed cases and Fresh evaluation 14/14. LangSmith queues contain 8 baseline and 7 focused completed run reviews, covering 14 distinct tickets, with 75 feedback records and zero pending. Approval records review completion rather than changing a prediction into a correct result.

The v3 experiment stores 100 traces, 100 Exact Match scores, 100 rubric-v1 scores, 100 rubric-v2 scores and a separate human t033 feedback item. Cloud values were read back and verified, including preservation of the old automated t033 score.

[Open the baseline, focused and v3 LangSmith comparison](https://smith.langchain.com/o/b21f8ce6-e07f-4579-b2f2-b4ca372647f3/datasets/b97bfa75-95ea-4c09-b9b9-cbb8493da698/compare?selectedSessions=b2f408bc-391e-49a4-bb96-58ba78619308%2Cf1866797-b7bb-48c1-963a-2b154308d4fd%2C7ee03a10-f2a3-4c15-99f4-4dc902378b53). Account/workspace access is required.

## Reproduce the saved analysis

Run `python finalize_submission.py` or execute all cells in the main notebook. These operations read saved evidence and make no model/API calls. Run `python verify_submission.py` from the repository root to validate historical approvals, preserved hashes, final metrics, notebook execution and report links.

Original classifiers and optional live LangSmith commands remain available in project.py. V3 code is in v3/experiment.py; grading is in v3/judge_v3.py and v3/judge_v2.py. Live runs require local OpenAI/LangSmith credentials and dependencies in requirements.txt. No keys are committed. Windows DPAPI storage can be configured with credentials.ps1; saved credentials are specific to the local Windows account. Offline analysis does not require credentials. Machine-specific CA bundles and environments are excluded.

Archived source snapshots and older judge manifests describe their original execution dates. The latest documents intentionally supersede their old conclusions while preserving raw inputs, predictions, historical labels, approvals and scores.

## Sources

The supplied Evaluations Using LangSmith handout links to [The Gen Academy customer-support repository](https://github.com/The-Gen-Academy/4A-Customer-Support-Agent-Evaluation), commit ef517b274cf86a2c4fa8ae72fdc89b3dce80f41d. The initially shared 4B social-media repository is a different assignment. The upstream broader-revision 92%→97% comparison is historical source context and is separate from the focused/v3 experiment reported here.

## Artifact checks

The final notebook executes six code cells offline and verifies preserved historical source hashes. The PowerPoint has ten rendered slides, editable tables and passing package/layout checks. Word text has 537 narration words, a 176-word demo and exactly 20 summary points. A five-page layout proof was inspected; native Word pagination is unverified because the packaged LibreOffice renderer is unavailable.
