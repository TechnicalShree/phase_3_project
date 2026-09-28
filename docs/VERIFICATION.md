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

- Native Provider API and OpenRouter runs remain unverified. Command Code Go rejects Provider API calls with `403 upgrade_required`; its CLI is tested separately below.
- Publish the repository publicly or share it with the instructor, then submit its GitHub URL. The local build has not been published or submitted.

## Command Code provider update

The factory now selects Command Code or OpenRouter without adding a dependency. The provider-selection check verifies URL, model and key isolation for both providers, the UI health metadata, missing-key errors, and rejection of unknown providers. It also verifies that a temperature override is omitted for models that do not support it. The complete suite now has **17 passing checks**. Live provider calls still require a configured key and are not included in this claim.


## Command Code Go CLI adapter

Installed `command-code@1.66.0` inside the ignored `.venv/commandcode` directory. Go authentication succeeded through the documented headless CLI with `stealth/space-bunny-alpha`; the same account's direct Provider API returned `403 upgrade_required`.

The adapter validates JSON against Pydantic schemas and converts allowed tool decisions into LangGraph tool calls. It disables CLI tools through a mod, uses temporary working directories, passes credentials through the environment, and does not persist CLI sessions. Native API function calling is not claimed for this transport. LangGraph owns execution, persistence and approvals.

The suite has **18 passing checks**, including CLI schema validation, unknown-tool/argument rejection, required draft enforcement, timeout/nonzero-exit handling, and secret-free error messages. The initial live smoke attempt passed lookup/specialists but hit the one-turn CLI limit during the second request; the limit was increased to two while retaining the 90-second timeout and rejecting unsuccessful results.

The complete live smoke retry **passed** using Space Bunny Alpha on Go: real classification, supervisor routing, account/service lookup execution, three specialist findings, validated ticket draft, approval interrupt, and denial with zero ticket records. The live test used a temporary SQLite directory. Native API providers remain unverified.

## Public HTTPS browser end-to-end test (2026-09-28)

Tested the deployed `https://campus-it.technicalshree.in/` through the browser UI, using fictional records:

- Fresh visitor: the access-token panel opens at the top; invalid credentials are rejected, valid app token connects. Authentication remains enforced.
- Submitted Wi-Fi outage through the streaming form; observed actual tool execution and three specialist findings, then an approval pause.
- Reloaded the page while pending, edited the draft title, and approved it. Registry contains `IT-00001`, marked edited and approved.
- Submitted account deletion review and denied it; the UI confirmed no record was written and ticket count stayed at one.
- Inspected checkpoint history, replayed the denied request, and observed a fresh approval pause. Explicitly approving that replay created mock review ticket `IT-00002` (no account deletion).
- Submitted the prompt-injection example; it was blocked with zero agent steps.
- Duplicate approval via public API returned 409 without increasing ticket count; invalid authentication returned 401.
- Refreshed the deployed page and verified persisted records. The new browser test session had no console warnings or errors at the guardrail checkpoint.

Two deployment/UI issues were fixed: connection settings were hidden in the footer, and Cloudflare cached the old JavaScript. The connection panel is now prominent and static asset URLs are versioned. Tests rerun on EC2: **18 Python checks and both browser-helper checks passed**. E2E-labelled threads and two mock tickets are retained as evidence; no real accounts were modified.
