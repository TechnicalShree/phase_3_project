# Verification evidence

Verified locally on 2026-09-28 with Python 3.12.11 and the exact versions in `requirements.txt`.

## Automated checks

Command: `python -m unittest discover -s tests -v`

**16 checks passed**, including:

| Evidence | What it establishes |
| --- | --- |
| Four routing cases | Typed graph reaches the correct campus category |
| Bound-tool messages | Knowledge base, account lookup and service-status calls execute through ToolNode |
| Adversarial ReAct doubles | Duplicate calls and unique-call loops hit explicit circuit breakers |
| Separate-process continuation | SQLite conversation history survives Python process exit |
| Real HTTP server kill/restart | A pending interrupt survives forced Uvicorn termination, resumes, and accepts a follow-up |
| Seven-turn context checks | Active history/messages shrink and summary is populated, including blocked turns |
| Pre-model/pre-storage guardrails | Blocked requests never construct the model; sample PII is absent from every stored checkpoint |
| Standalone subgraphs | Triage and research compile and run without the parent graph |
| Supervisor cap | The cap fires before another model call |
| Three-worker barrier | Specialist execution is concurrent and findings remain distinct |
| Review API checks | Approve, deny, edit-and-approve, stale reviews, restart resume, and idempotency behave correctly |
| Controlled corruption/replay | Anomaly origin and parent found; original state unchanged; replay needs fresh approval |
| Boundary validation | Unauthorized access, extra approval/state fields and cross-origin mutations rejected |
| Live-mode unit checks | Critical requests retain high severity even if a model suggests low; injected write state stays out of the model schema |

No live provider call is included in these offline results. `scripts/live_smoke.py` is the opt-in live verification command once a key is available.

## Browser checks

A fresh isolated Chrome context was used against the actual local FastAPI server:

- Submitted the Wi-Fi example through the streaming form and observed agent/tool/specialist events.
- Edited the proposed title and approved it; the registry count increased and approval queue cleared.
- Created a fault, selected its parent using Find bad checkpoint, replayed the correction and observed fresh approval pending.
- Checked a 390px mobile viewport: document width equaled viewport width, with no horizontal overflow.
- Checked the browser console after reload: no warnings or errors.

The README screenshot is an actual running UI capture, not a design mockup.

## Reproducibility

A fresh local clone of source commit `0f25be0` was created outside the working tree. A new Python virtual environment was created with `python -m venv`, all pinned requirements were installed with pip, and the full suite ran from that clone: **16 checks passed in 5.105 seconds**. No reference PDFs, local `.env`, working-tree database or existing virtual environment were copied into it. The evidence commit immediately after that source revision changed documentation/screenshots only. Later provider changes are checked separately below.

The complete captured output is in [test-results.txt](test-results.txt).

## Remaining external steps

- Configure a Command Code or OpenRouter key and run the opt-in live smoke test. Do not claim live verification until it passes.
- Publish the repository publicly or share it with the instructor, then submit its GitHub URL. The local build has not been published or submitted.

## Command Code provider update

The factory now selects Command Code or OpenRouter without adding a dependency. The provider-selection check verifies URL, model and key isolation for both providers, the UI health metadata, missing-key errors, and rejection of unknown providers. It also verifies that a temperature override is omitted for models that do not support it. The complete suite now has **17 passing checks**. Live provider calls still require a configured key and are not included in this claim.
