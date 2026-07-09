# AI News Reporter

An agentic AI system built on **Google Cloud's Agent Development Kit (ADK)** that researches AI innovations, analyzes public sentiment, and generates a structured markdown report — fully automated through a multi-agent pipeline.

---

## What It Does

Given a topic query (e.g. "AI innovations in healthcare"), the system:

1. **Fetches** relevant news articles using Google Search grounding
2. **Analyzes** sentiment and evaluates the innovation's future potential
3. **Generates** a polished, structured README-style report in markdown

All three steps run automatically in sequence with no manual handoff between agents.

---

## Architecture

```
User Query
    │
    ▼
SequentialAgent (AI_News_Orchestrator_Agent)
    │
    ├── [1] ai_news_fetcher_subagent
    │       Model: gemini-2.5-flash (global endpoint)
    │       Tools: GoogleSearchTool
    │       Output: saves articles → session state key `articles`
    │
    ├── [2] sentiment_and_evaluator_subagent
    │       Model: gemini-2.5-flash (global endpoint)
    │       Tools: url_context
    │       Input: reads `articles` from session state
    │       Output: saves analysis → session state key `analysis`
    │
    └── [3] reporter_subagent
            Model: gemini-2.5-flash (global endpoint)
            Tools: none
            Input: reads `articles` + `analysis` from session state
            Output: saves final markdown report → session state key `report`
```

### Key Design Decisions

**`SequentialAgent` as the root** — instead of an `LlmAgent` orchestrator. The `SequentialAgent` chains sub-agents in strict order without making its own LLM call, which avoids Vertex AI's restriction against mixing search grounding tools with function tools in the same API request.

**`output_key` for state sharing** — each sub-agent saves its final response to a named session state key. Downstream agents reference these keys using `{key}` template syntax in their instructions, making data flow reliable and explicit rather than relying on the LLM to relay outputs.

**`GlobalGemini` model wrapper** — all agents use a custom `Gemini` subclass that pins the Vertex AI client to the `global` endpoint. `gemini-2.5-flash` is only served from `global`; the default ADK client uses the regional endpoint (e.g. `us-west1`) and fails with a model-not-found error.

---

## Project Structure

```
ai_news_reporter/
├── agent.py          # All agent definitions and pipeline
├── __init__.py       # Package entry point
├── .env              # Environment configuration (not committed)
├── .gitignore
└── README.md         # This file
```

---

## Setup

### Prerequisites

- Python 3.11+
- Google Cloud project with Vertex AI API enabled
- ADK installed: `pip install google-adk`

### Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_GENAI_USE_ENTERPRISE=1
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-west1
```

`GOOGLE_GENAI_USE_ENTERPRISE=1` tells the ADK to use Vertex AI instead of the public Gemini API.

### Authentication

```bash
gcloud auth application-default login
gcloud config set project your-project-id
```

### Run

```bash
# From the parent directory (one level above ai_news_reporter/)
adk run ai_news_reporter
```

---

## Usage

Once running, type any AI innovation topic as your query:

```
[user]: latest AI innovations in healthcare
[user]: AI in robotics and manufacturing
[user]: large language model breakthroughs 2025
```

The system will run through all three agents automatically and return a formatted markdown report covering:

- Executive summary
- News coverage overview with source links
- Sentiment analysis (scores, themes, distribution)
- Future potential assessment (scored criteria table + verdict)
- References and conclusion

---

## Agent Details

### Fetcher Agent (`ai_news_fetcher_subagent`)

Uses Google Search grounding to find at least 3 relevant articles. Has a multi-strategy fallback: direct search → expanded query → category-based search. Returns structured JSON saved to session state as `articles`.

### Sentiment & Evaluator Agent (`sentiment_and_evaluator_subagent`)

Reads `{articles}` from session state and performs two tasks:
- **Sentiment Analysis**: scores each article −1 to +1, aggregates distribution, identifies top positive/negative themes
- **Future Potential Evaluation**: scores the innovation across 6 criteria (novelty, market viability, scalability, ethical impact, competitive advantage, adoption barriers) and returns a verdict: HIGH / MEDIUM / LOW / TOO EARLY TO TELL

Has access to `url_context` for fetching full article content when needed.

### Reporter Agent (`reporter_subagent`)

Reads both `{articles}` and `{analysis}` from session state and synthesizes them into a structured markdown report following a fixed template. No tools — pure synthesis.

---

## From Cloud UI to Local Development

### The Original Vision

The initial approach was to build this entirely through the **Vertex AI Agent Designer** — a visual, drag-and-drop UI for creating and connecting agents on Google Cloud. The idea was appealing: no code needed for the wiring, pre-built Gemini integration, and one-click deployment to Cloud Run.

The intended workflow looked like this:

```
User Query
    ↓
Vertex AI Agent Designer (visual interface)
    ↓
Drag & Drop: Fetcher → Sentiment & Evaluator → Reporter
    ↓
Cloud Storage (BigQuery / Firestore)
    ↓
Complete Report
```

### Why It Didn't Work Out

**1. GoogleSearchTool returned nothing**
The `GoogleSearchTool` in Agent Designer kept returning empty results for every query — even something as broad as "latest AI healthcare innovations." There was no useful error message, just the agent's fallback response. This made the fetcher useless from the start.

**2. No automatic data flow between agents**
Agent Designer's state management didn't work as expected. Each agent ran in isolation — the fetcher's JSON output never arrived at the sentiment agent. The UI implied automatic handoff, but in practice the agents were stateless and disconnected.

**3. Dependency conflicts in local ADK setup**
When moving toward local development, package version conflicts surfaced immediately:
```
AttributeError: module 'anthropic.types' has no attribute 'ToolParam'
```
ADK was trying to import Anthropic/Claude model code that wasn't needed, and version mismatches between `anthropic`, `pydantic`, and ADK caused failures on startup.

**4. Authentication failures**
```
google.auth.exceptions.DefaultCredentialsError: Your default credentials were not found.
```
Local ADK requires `gcloud auth application-default login` and specific IAM roles (Vertex AI User, Storage Admin). The environment variables also weren't wired up correctly initially.

**5. Agent Designer's debugging tools were too limited**
Error messages from the UI were cryptic, data mapping between agents was unclear, and there was no way to inspect what was actually being passed between steps. Iteration was slow because every change required a cloud deployment.

### Why Local Development Won

Switching to local `adk run` solved most of these problems immediately:

| Pain Point | Cloud UI | Local ADK |
|---|---|---|
| Debugging | Cryptic UI errors | Full Python stack traces |
| Iteration speed | Cloud deploy each time | Instant on save |
| Data flow visibility | Black box | Inspectable via logs |
| Search reliability | Broken / empty results | Fixed once tool wiring was correct |
| State management | Unclear, implicit | Explicit `output_key` + `{key}` templates |

The tradeoff is that local development requires understanding the ADK API directly — which is where the errors documented in the next section came in.

---

## Lessons Learned: Errors We Hit and What They Taught Us

### 1. No State Between Agents — The Pipeline Was Broken From the Start

**What happened:** The original design used an `LlmAgent` orchestrator with `sub_agents`. The orchestrator's instruction told it to "pass the output of agent 1 to agent 2, then agent 3." The fetcher and sentiment agents ran fine, but the reporter never received the data — it produced either nothing or a vague generic report.

**Why:** When an LLM orchestrator relays data between agents verbally, it paraphrases and truncates. Large structured JSON outputs don't survive being re-summarized by a language model. The reporter was effectively working blind.

**Fix:** ADK's `output_key` parameter saves an agent's final response directly to session state. Downstream agents read it back via `{key}` template substitution in their instruction. The data flows exactly, not through a lossy LLM relay.

---

### 2. `GoogleSearchTool` Cannot Be Mixed With Other Tool Types

**Error:**
```
google.genai.errors.ClientError: 400 INVALID_ARGUMENT.
'Multiple tools are supported only when they are all search tools.'
```

**What happened:** The fetcher agent was given both `GoogleSearchTool()` and `url_context` as tools. Vertex AI rejected the API request immediately.

**Why:** `GoogleSearchTool` is a *grounding tool* — it modifies how the model generates responses by attaching live search results. Vertex AI does not allow grounding tools to be combined with function-type tools (like `url_context`) in the same request. They are fundamentally different tool categories at the API level.

**Fix:** Each agent can only hold one tool type. `GoogleSearchTool` goes on the fetcher alone. `url_context` goes on the sentiment agent alone. Agents that need both capabilities must be split.

---

### 3. Using `LlmAgent` as Orchestrator With Sub-Agents That Have `GoogleSearchTool`

**Error:** Same `400 INVALID_ARGUMENT` — but now from the *orchestrator*, even after fixing the fetcher.

**What happened:** Even with the fetcher fixed to only have `GoogleSearchTool`, the `LlmAgent` orchestrator that listed it in `sub_agents` still crashed.

**Why:** When ADK converts `sub_agents` into callable tools for the orchestrator's LLM call, it builds a combined tool list. The orchestrator ends up with function-type transfer tools (one per sub-agent) alongside the fact that one sub-agent uses `GoogleSearchTool`. Vertex AI sees a mixed tool configuration and rejects the request.

**Fix:** Replace the `LlmAgent` orchestrator with `SequentialAgent`. A `SequentialAgent` is a pure coordinator — it runs sub-agents in order without making an LLM call itself. There's no combined tool list, no mixed-type conflict, and no ambiguity about execution order.

---

### 4. Nested `AgentTool` Wrappers Silently Kill Search

**What happened:** The original file wrapped `GoogleSearchTool` inside a dedicated `LlmAgent` (e.g. `ai_news_fetcher_subagent_google_search_agent`), then wrapped *that* agent in an `AgentTool` attached to the fetcher. Every search silently returned the fallback "I couldn't find articles" message.

**Why:** `GoogleSearchTool` is a grounding tool that must be attached directly to the model making the API call. Wrapping it in an `AgentTool` severs that direct connection — the grounding never activates, the inner agent receives no search results, and the outer agent gets empty responses it can't distinguish from genuine failures.

**Fix:** Attach `GoogleSearchTool()` directly to the agent that needs it. No wrappers.

---

### 5. Regional Endpoint Doesn't Serve the Latest Models

**What happened (anticipated):** The `.env` sets `GOOGLE_CLOUD_LOCATION=us-west1`. Using `model='gemini-2.5-flash'` as a plain string would route requests to the `us-west1` regional endpoint, which may not serve the latest model versions.

**Why:** Cutting-edge Gemini models are rolled out to the `global` endpoint first. Regional endpoints lag behind or may never serve certain model versions.

**Fix:** The `GlobalGemini` wrapper class overrides the default ADK `Gemini` model's `api_client` property to pin `location="global"`. All agents use `GlobalGemini(model='gemini-2.5-flash')` instead of a bare model string.

---

## Summary of Architecture Principles

| Principle | Why |
|-----------|-----|
| Use `SequentialAgent` for ordered pipelines | Avoids LLM orchestrator overhead and tool-type conflicts |
| Use `output_key` + `{key}` templates for data flow | Reliable, lossless — no LLM relay needed |
| One tool type per agent | Vertex AI rejects mixed search + function tool lists |
| Always use `GlobalGemini` for latest models | Regional endpoints may not serve cutting-edge model versions |
| Attach grounding tools directly, never via AgentTool | Grounding tools must be on the model making the API call |
