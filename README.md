# AI-Powered Customer Support Agent — Intelligent Copilot for Support Teams

> A production-grade AI system that generates context-aware draft replies for customer support agents — powered by LangGraph agent orchestration, Retrieval-Augmented Generation (RAG), and persistent per-customer memory.

---

## Overview

Support agents spend hours writing replies to repetitive tickets. This system eliminates that friction.

When a ticket comes in, the AI copilot instantly pulls together everything it knows — your company's policies, the customer's past interactions, their subscription plan, and their current ticket load — and drafts a precise, empathetic reply. The agent reviews it, makes any edits, and sends it. When they accept a draft, the resolution is saved to memory and used to make future replies even better.

**The result:** faster response times, consistent quality, and a support team that focuses on judgment — not typing.

---

## How It Works

```
Customer submits a ticket
          │
          ▼
┌─────────────────────┐
│   Support Dashboard  │  ← Agent sees ticket + customer info
└────────┬────────────┘
         │  Agent clicks "Generate Draft"
         ▼
┌─────────────────────────────────────────────────────┐
│                    AI Copilot                        │
│                                                     │
│  1. Search Memory         2. Search Knowledge Base  │
│  "Has this customer       "What does company policy │
│   had this issue           say about this topic?"   │
│   before?"                 (ChromaDB RAG)           │
│  (Mem0 + ChromaDB)                                  │
│                                                     │
│  3. Check Customer Plan & Ticket Load               │
│  "Is this a Pro customer? How many open tickets?"   │
│  (LangGraph Agent + Tools)                          │
│                                                     │
│  4. Generate Draft Reply                            │
│  (Groq LLM — fast, empathetic, under 180 words)     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
            Agent reviews the draft
                       │
          ┌────────────┴────────────┐
          │                         │
     Accept draft               Edit & send
          │
          ▼
  Resolution saved to memory
  (used next time this customer writes in)
```

---

## System Architecture

![System Architecture](architecturediagram.png)

The system is built in four clean layers:

- **Presentation Layer** — FastAPI routes serve the REST API; Streamlit powers the agent-facing dashboard
- **Application Layer** — The copilot service orchestrates all AI components: memory retrieval, knowledge search, tool calls, and draft generation
- **Infrastructure Layer** — Modular integrations for the LLM (Groq), vector stores (ChromaDB), customer memory (Mem0), and the SQLite database
- **Data Stores** — Three separate stores: `support.db` for tickets/customers/drafts, `chroma_mem0` for per-customer memories, and `chroma_rag` for knowledge base vectors

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | [Groq](https://groq.com) (Llama 3.1) |
| Agent Framework | LangGraph + LangChain |
| Knowledge Base | ChromaDB (vector search) |
| Customer Memory | Mem0 (per-customer history) |
| Embeddings | OpenAI text-embedding-3-small |
| Backend API | FastAPI |
| Dashboard UI | Streamlit |
| Database | SQLite |
| Deployment | Docker + AWS EC2 |

---

## Project Structure

```
├── customer_support_agent/
│   ├── api/              → REST API endpoints (FastAPI)
│   ├── core/             → Configuration and settings
│   ├── integrations/
│   │   ├── memory/       → Customer memory store (Mem0)
│   │   ├── rag/          → Knowledge base search (ChromaDB)
│   │   └── tools/        → AI agent tools (plan lookup, ticket load)
│   ├── repositories/     → Database access (SQLite)
│   ├── schemas/          → Request/response data models
│   └── services/         → Core business logic (AI copilot)
├── knowledge_base/       → Your FAQ and policy documents (.md files)
├── dashboard.py          → Streamlit UI
├── docker-compose.yml    → Run everything with one command
└── .env.example          → Environment variable template
```

---

## Getting Started

**1. Clone the repo**
```bash
git clone <your-repo-url>
cd AI-Powered-Customer-Support-Agent
```

**2. Set up your API keys**
```bash
cp .env.example .env
# Open .env and fill in your GROQ_API_KEY and OPENAI_API_KEY
```

**3. Run with Docker**
```bash
docker compose up --build
```

**4. Open the app**
- Dashboard UI → `http://localhost:8501`
- API docs → `http://localhost:8000/docs`

---

## Adding Your Knowledge Base

Drop `.md` or `.txt` files into the `knowledge_base/` folder, then call:

```
POST /knowledge/ingest
```

The AI will now use your documents when generating replies.

---

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key for the LLM |
| `OPENAI_API_KEY` | OpenAI API key for embeddings |
| `GROQ_MODEL` | Model to use (default: `llama-3.1-8b-instant`) |

See [.env.example](.env.example) for the full list.

---

## Deployment

Includes a GitHub Actions CI/CD pipeline that deploys to AWS EC2 on every push to `main`.
See [docs/EC2_deployment_flow.md](docs/EC2_deployment_flow.md) for setup instructions.
