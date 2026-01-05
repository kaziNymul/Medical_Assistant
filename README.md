# AI Clinical Documentation Assistant — From Scratch Build (RAG + Agents + AWS Bedrock + Databricks)

## Purpose of This Repo

This repository contains a **healthcare-grade AI Clinical Documentation Assistant**.
It will be built **step-by-step from scratch**, evolving from a simple local RAG assistant into a cloud-integrated system.

The final goal is to support workflows like:

- extracting structured information from clinical-style notes
- pre-filling registry or workflow forms
- providing explainable, auditable outputs
- operating ONLY on **masked / de-identified data**

The data is synthetic / Kaggle-based, but the **design must follow the same safety and privacy principles as real healthcare systems**.

This spec is written so GitHub Copilot always understands the architecture, terms, goals, safety rules, and implementation roadmap.

---

## SYSTEM DEVELOPMENT ROADMAP

We will build in 3 phases:

### **Phase 1 — Local Prototype (No Cloud Required)**

Goal:
- Local RAG pipeline
- Local vector index
- Local FastAPI backend

Stack:
- Python 3.11+
- FastAPI
- Sentence-Transformers
- FAISS (vector index)
- Local CSV/JSON data

---

### **Phase 2 — Add AWS Bedrock for LLM & Embeddings**

Goal:
- Replace local LLM with Claude 3.5 Sonnet
- Use Titan/Cohere embeddings
- Keep existing RAG pipeline

Stack additions:
- boto3
- AWS IAM credentials
- Bedrock enabled region

---

### **Phase 3 — Add Databricks for Data Engineering & Monitoring**

Goal:
- Treat data properly like a Lakehouse
- Add masking pipeline
- Add evaluation dashboards
- Store AI logs and metrics

Stack additions:
- Databricks
- Spark / Delta tables
- SQL analytics

---

# CORE ARCHITECTURE (TARGET STATE)

Kaggle data
↓
Databricks (Bronze → Silver → Gold)
↓
Masking / De-identification
↓
Chunking + Embeddings (Bedrock)
↓
Vector DB
↓
LangGraph agent workflow
↓
Claude 3.5 Sonnet (Bedrock)
↓
JSON structured output + evidence
↓
Doctor review (human-in-loop)
↓
Logs + evaluation stored in Databricks


---

# KEY CONCEPTS (Teach Copilot These Meanings)

## **Agent / Agentic Workflow**

An **agent** = a logical step powered by AI + tools.

We will use **LangGraph** to define:

- `RetrievalAgent` — retrieves chunks via vector search  
- `ExtractionAgent` — fills form fields  
- `ValidationAgent` — checks consistency & confidence  
- `ExplanationAgent` — generates human-friendly explanation  

Agents operate on **masked text only**.

---

## **AWS Bedrock**

AWS Bedrock provides AI models via API.

In this project:

### Reasoning Model
- **Claude 3.5 Sonnet**
  - Used by agents to:
    - read clinical notes
    - extract structured fields
    - generate JSON outputs
    - provide explanations
    - never hallucinate

### Embeddings
- **Titan Embeddings** or **Cohere embeddings**
  - Used for RAG retrieval

All calls go through boto3.

---

## **Databricks (Lakehouse Platform)**

Databricks is used when we reach Phase 3.

It handles:

- ingesting Kaggle data
- cleaning columns
- converting to Delta tables
- **masking personal identifiers**
- creating AI-ready Gold tables
- storing AI logs + metrics
- dashboards / monitoring

This simulates **real healthcare data engineering**.

---

# PRIVACY & MASKING REQUIREMENTS

Even though Kaggle data is synthetic:

### ALWAYS ASSUME DATA IS SENSITIVE

We must:

- NEVER store names / emails / addresses in plain text
- Remove identifiers before AI use
- Only send **minimum necessary** text to LLM
- Avoid storing raw notes in logs

Masking includes:

- replacing names with `[PATIENT_NAME]`
- replacing hospitals with `[HOSPITAL]`
- pseudonymizing IDs
- redacting email/phone patterns

This is CRITICAL to retain in all code paths.

---

# AI MODEL BEHAVIOR (MASTER SYSTEM PROMPT)

Copilot should reuse this logic when generating Bedrock prompts:

> “You are an AI Clinical Documentation Assistant working on de-identified patient data. Your job is to extract structured fields from clinical text and provide evidence citations. Never hallucinate. Never guess missing data. Do not generate personal identifiers. Return strict JSON output. Declare uncertainty when appropriate. AI output is always reviewed by clinicians.”

---

# DATA FLOW STAGES

## Stage 1 — Raw Kaggle Data

Stored locally or in Databricks Bronze.

## Stage 2 — Masked / De-identified Data

Remove identifiers.
Create pseudonymous IDs.

## Stage 3 — AI-Ready Documents

Chunk text into 500–1500-token blocks.

Store metadata:
- patient_id
- episode_id
- source
- date

## Stage 4 — Embeddings + Vector Store

Use Bedrock Titan/Cohere embeddings

Vector DB options:
- FAISS (local)
- pgvector
- OpenSearch
- Databricks vector search

## Stage 5 — AI Agents (LangGraph)

Agents coordinate tasks.

## Stage 6 — Output + Logging

Write logs to:
- local DB first
- later Databricks

Include:
- field values
- confidence
- evidence
- timestamp

---

# TECH STACK (DEFINED FOR COPILOT)

## Languages
- Python 3.11+

## Backend
- FastAPI
- Pydantic

## AI & Agents
- LangGraph
- LangChain
- AWS Bedrock (via boto3)
- Claude 3.5 Sonnet
- Titan / Cohere embeddings

## RAG
- Sentence-Transformers
- FAISS (V1 local)
- Vector DB (later)

## Data Platform (Phase 3)
- Databricks
- Delta Lake
- Spark SQL

## Deployment (optional later)
- Docker

---

# **DEVELOPMENT PHASES (IMPORTANT FOR COPILOT)**

### Phase 1 — Implement Local RAG First

Tasks:
- create `data/` folder
- load Kaggle CSV
- clean it into JSONL
- build FAISS index
- add FastAPI endpoint
- call any temporary LLM
- enforce masking

This establishes the core flow.

---

### Phase 2 — Replace LLM with AWS Bedrock

Tasks:
- configure AWS credentials
- add boto3 calls
- update prompts
- enforce JSON output
- handle retries & errors

Now the assistant uses Claude.

---

### Phase 3 — Add Databricks Lakehouse

Tasks:
- ingest data into Delta tables
- add masking job
- create Gold AI docs
- log AI predictions
- analyze metrics

This simulates **enterprise healthcare AI operations**.

---

# HUMAN-IN-THE-LOOP RULE

Doctors always review outputs.

The system NEVER:
- prescribes medication
- diagnoses disease
- makes decisions

It ONLY:
- extracts facts
- summarizes
- assists documentation

---

# MASTER JSON OUTPUT CONTRACT

All LLM outputs MUST be JSON:

```json
{
  "primary_diagnosis": "...",
  "latest_hba1c": "...",
  "hba1c_trend": "...",
  "medications": ["..."],
  "smoking_status": "...",
  "complications": [],
  "data_completeness": "complete | partial | missing",
  "confidence_score": 0.0,
  "evidence": [
    {
      "field": "primary_diagnosis",
      "quote": "...",
      "source_type": "discharge_summary",
      "date": "2025-01-01"
    }
  ],
  "clinical_explanation": "...",
  "pii_detected": false
}

If unknown → return null.

No hallucinations.

MCP (MODEL CONTEXT PROTOCOL) — NOTE FOR FUTURE

MCP is optional.

If implemented later:

Databricks queries

Vector search

Registry APIs

can be exposed as MCP tools.

But do not implement MCP now unless requested.

PROJECT GOAL SUMMARY

This repo demonstrates:

healthcare-aware AI safety

RAG + embeddings

Bedrock LLM orchestration

agentic architecture

masking & governance

Databricks-style data engineering

explainable JSON outputs

realistic medical workflows

human-in-loop AI

All built iteratively from zero.
