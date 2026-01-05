# 🏥 AI Clinical Documentation Assistant

> Healthcare-grade AI system for extracting structured clinical data from any document format using multi-agent workflows, local LLM extraction, and enterprise data governance.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![CrewAI](https://img.shields.io/badge/CrewAI-1.7.2-orange.svg)](https://www.crewai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ Features

- **🤖 5-Agent CrewAI Workflow** — Intelligent case analysis with specialized agents for retrieval, extraction, validation, explanation, and routing
- **📄 Universal File Parser** — Supports PDF, Word, Excel, CSV, JSON, XML, HL7, FHIR, CDA, and Images (OCR)
- **🧠 Local LLM Extraction** — CPU-optimized FLAN-T5 for clinical data extraction without cloud dependency
- **☁️ AWS Bedrock Integration** — Claude 3 Haiku for reasoning + Titan Embeddings V2 for semantic search
- **🔍 FAISS Vector Store** — 55,500+ indexed clinical documents with fast similarity search
- **🔒 PHI/PII Masking** — Automatic detection and masking of protected health information
- **🏦 HashiCorp Vault** — Secure secrets management for credentials and API keys
- **📊 Databricks Sync** — Unity Catalog integration with masked/unmasked table separation
- **🎨 Modern React UI** — Dashboard, Query, Case Brief, Smart Extract, and Document Management

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph Frontend["🖥️ Frontend (React + Vite)"]
        Dashboard[📊 Dashboard]
        Query[🔍 Query]
        CaseBrief[📋 Case Brief]
        SmartExtract[🧠 Smart Extract]
        Documents[📁 Documents]
    end

    subgraph API["⚡ FastAPI Backend"]
        QueryAPI["/api/query"]
        CrewAPI["/api/crew"]
        ExtractAPI["/api/extract"]
        DocsAPI["/api/documents"]
    end

    subgraph Core["🔧 Core Services"]
        RAG["RAG Pipeline"]
        CrewAI["CrewAI Agents"]
        Extractor["LLM Extractor"]
        Masking["PII Masking"]
    end

    subgraph Storage["💾 Data Layer"]
        FAISS[(FAISS\n55,500 docs)]
        SQLite[(SQLite\nPII Store)]
        Vault[(HashiCorp\nVault)]
    end

    subgraph Cloud["☁️ Cloud Services"]
        Bedrock["AWS Bedrock\nClaude 3 Haiku"]
        Titan["Titan Embeddings\nV2 1024-dim"]
        Databricks["Databricks\nUnity Catalog"]
    end

    Frontend --> API
    API --> Core
    Core --> Storage
    Core --> Cloud

    style Frontend fill:#e1f5fe
    style API fill:#fff3e0
    style Core fill:#f3e5f5
    style Storage fill:#e8f5e9
    style Cloud fill:#fce4ec
```

---

## 🔄 Data Flow Architecture

```mermaid
flowchart LR
    subgraph Input["📥 Input Sources"]
        PDF[PDF]
        Word[Word]
        HL7[HL7/FHIR]
        CSV[CSV/Excel]
        Images[Images]
    end

    subgraph Parser["📄 Universal Parser"]
        FileParser[File Parser]
        OCR[Tesseract OCR]
    end

    subgraph Processing["⚙️ Processing"]
        Masking[PII Masking]
        Chunking[Text Chunking]
        Embedding[Titan Embeddings]
    end

    subgraph Storage["💾 Storage"]
        FAISS[(FAISS Index)]
        PII[(PII Database)]
        Vault[(Vault Secrets)]
    end

    subgraph AI["🤖 AI Layer"]
        LocalLLM[FLAN-T5 Base]
        Bedrock[Claude 3 Haiku]
        CrewAI[CrewAI Agents]
    end

    subgraph Output["📤 Output"]
        JSON[Structured JSON]
        Databricks[(Databricks)]
        UI[React UI]
    end

    Input --> Parser
    Parser --> Processing
    Processing --> Storage
    Storage --> AI
    AI --> Output

    style Input fill:#ffebee
    style Parser fill:#fff8e1
    style Processing fill:#e8f5e9
    style Storage fill:#e3f2fd
    style AI fill:#f3e5f5
    style Output fill:#e0f2f1
```

---

## 🤖 CrewAI Multi-Agent Workflow

```mermaid
flowchart TD
    Start([🚀 Clinical Query]) --> Retrieval

    subgraph Agents["CrewAI Agent Workflow"]
        Retrieval["🔍 Retrieval Agent\n─────────────────\nSearches FAISS index\nFinds relevant documents"]
        Extraction["📋 Extraction Agent\n─────────────────\nExtracts structured data\nDiagnoses, medications, labs"]
        Validation["✅ Validation Agent\n─────────────────\nChecks completeness\nValidates consistency"]
        Explanation["💬 Explanation Agent\n─────────────────\nGenerates summaries\nHuman-readable output"]
        Routing["🔀 Routing Agent\n─────────────────\nRoutes to workflows\nPrioritizes cases"]
    end

    Retrieval --> Extraction
    Extraction --> Validation
    Validation --> Explanation
    Explanation --> Routing
    Routing --> End([📊 Structured Output])

    style Retrieval fill:#bbdefb
    style Extraction fill:#c8e6c9
    style Validation fill:#fff9c4
    style Explanation fill:#f8bbd9
    style Routing fill:#d1c4e9
```

---

## 🔐 Security Architecture

```mermaid
flowchart TB
    subgraph Input["Raw Data Input"]
        RawData[("📄 Clinical Documents\nwith PHI/PII")]
    end

    subgraph Masking["🔒 PII Detection & Masking"]
        Detect["Detect PHI Entities"]
        Mask["Apply Masking Rules"]
        Store["Store Mapping in Vault"]
    end

    subgraph MaskedEntities["Masked Entities"]
        Name["[PATIENT_NAME]"]
        SSN["[SSN]"]
        DOB["[DOB]"]
        Phone["[PHONE]"]
        Email["[EMAIL]"]
        MRN["[MRN]"]
    end

    subgraph Secure["🔐 Secure Storage"]
        Vault[("HashiCorp Vault\nSecrets & Mappings")]
        PIIDb[("SQLite\nPII Database")]
    end

    subgraph Output["Safe Output"]
        MaskedDocs["Masked Documents"]
        Databricks["Databricks\nMasked Tables"]
    end

    RawData --> Detect
    Detect --> Mask
    Mask --> MaskedEntities
    Mask --> Store
    Store --> Secure
    MaskedEntities --> Output

    style Input fill:#ffcdd2
    style Masking fill:#fff9c4
    style MaskedEntities fill:#e1f5fe
    style Secure fill:#c8e6c9
    style Output fill:#d1c4e9
```

---

## 📊 Databricks Integration

```mermaid
flowchart LR
    subgraph Source["📥 Source Data"]
        Extractions[Clinical Extractions]
        Metadata[Document Metadata]
    end

    subgraph Sync["🔄 Databricks Sync"]
        SyncService["databricks_sync.py"]
    end

    subgraph Unity["📊 Unity Catalog"]
        subgraph Catalog["medical_ai"]
            subgraph Schema["clinical_data"]
                Unmasked[("clinical_extractions_unmasked\n────────────────\n🔴 Contains PHI\n🔒 Restricted Access")]
                Masked[("clinical_extractions_masked\n────────────────\n🟢 PHI Removed\n📊 Analytics Safe")]
            end
        end
    end

    subgraph Access["👥 Access Control"]
        Clinicians["👨‍⚕️ Clinicians\nFull Access"]
        Analysts["📊 Analysts\nMasked Only"]
        AI["🤖 AI Systems\nMasked Only"]
    end

    Source --> Sync
    Sync --> Unity
    Unmasked --> Clinicians
    Masked --> Analysts
    Masked --> AI

    style Unmasked fill:#ffcdd2
    style Masked fill:#c8e6c9
```

---

## 🧠 Local LLM Extraction Pipeline

```mermaid
flowchart TD
    subgraph Upload["📤 File Upload"]
        File["Any File Format"]
    end

    subgraph Parse["📄 Universal Parser"]
        Detect["Detect Format"]
        Extract["Extract Text"]
        OCR["OCR if Image"]
    end

    subgraph LLM["🧠 FLAN-T5 Extraction"]
        Prompt["Build Extraction Prompt"]
        Inference["CPU Inference\n~2-5 seconds"]
        Parse2["Parse JSON Output"]
    end

    subgraph Fields["📋 Extracted Fields"]
        Demographics["Demographics\nName, DOB, MRN"]
        Diagnoses["Diagnoses\nICD codes, descriptions"]
        Medications["Medications\nDrugs, dosages"]
        Labs["Lab Results\nValues, dates"]
        Vitals["Vital Signs\nBP, HR, Temp"]
        Plan["Assessment & Plan"]
    end

    subgraph Output["📤 Output"]
        JSON["Structured JSON"]
        Masked["Masked Version"]
        DB["Save to Database"]
    end

    Upload --> Parse
    Parse --> LLM
    LLM --> Fields
    Fields --> Output

    style Upload fill:#e3f2fd
    style Parse fill:#fff8e1
    style LLM fill:#f3e5f5
    style Fields fill:#e8f5e9
    style Output fill:#fce4ec
```

---

## 🖥️ Frontend Component Architecture

```mermaid
flowchart TB
    subgraph App["React Application"]
        Router["React Router"]
    end

    subgraph Pages["📄 Pages"]
        Dashboard["📊 Dashboard\n────────────\nStats & Metrics\nRecent Activity"]
        Query["🔍 Query\n────────────\nRAG Search\nBedrock LLM"]
        CaseBrief["📋 Case Brief\n────────────\nCrewAI Analysis\nStructured Output"]
        Extract["🧠 Smart Extract\n────────────\nLocal LLM\nFile Upload"]
        Docs["📁 Documents\n────────────\nDocument List\nUpload/Manage"]
        Settings["⚙️ Settings\n────────────\nConfiguration\nAPI Keys"]
    end

    subgraph Components["🧩 Components"]
        Layout["Layout"]
        Sidebar["Sidebar"]
        Cards["Cards"]
        Forms["Forms"]
    end

    subgraph State["📦 State Management"]
        TanStack["TanStack Query"]
        LocalState["React State"]
    end

    subgraph API["🔌 API Layer"]
        ApiClient["api.js"]
    end

    Router --> Pages
    Pages --> Components
    Pages --> State
    State --> API

    style App fill:#e3f2fd
    style Pages fill:#fff8e1
    style Components fill:#e8f5e9
    style State fill:#f3e5f5
    style API fill:#fce4ec
```

---

## 🔌 Infrastructure Deployment

```mermaid
flowchart TB
    subgraph Docker["🐳 Docker Compose"]
        subgraph Backend["Backend Container"]
            FastAPI["FastAPI :8000"]
            Python["Python 3.11"]
        end
        
        subgraph Frontend["Frontend Container"]
            Vite["Vite Dev :5173"]
            React["React 18"]
        end
        
        subgraph Services["Service Containers"]
            VaultC["HashiCorp Vault :8200"]
        end
    end

    subgraph Volumes["📁 Volumes"]
        Data["./data"]
        FAISS["./data/faiss_index"]
        Models["./models"]
    end

    subgraph External["☁️ External Services"]
        AWS["AWS Bedrock"]
        DB["Databricks"]
    end

    Docker --> Volumes
    Backend --> External
    
    style Docker fill:#e3f2fd
    style Volumes fill:#fff8e1
    style External fill:#fce4ec
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- AWS credentials configured (for Bedrock)
- HashiCorp Vault (optional, for secrets)

### Installation

```bash
# Clone the repository
git clone git@github.com:kaziNymul/Medical_Assistant.git
cd Medical_Assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Setup environment
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

Create a `.env` file with:

```env
# AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0

# HashiCorp Vault
VAULT_ADDR=http://127.0.0.1:8200
VAULT_TOKEN=your_vault_token

# Databricks (optional)
DATABRICKS_HOST=your_workspace.cloud.databricks.com
DATABRICKS_TOKEN=your_token
DATABRICKS_CATALOG=medical_ai
DATABRICKS_SCHEMA=clinical_data

# Local LLM
EXTRACTION_MODEL=google/flan-t5-base
EXTRACTION_DEVICE=cpu
```

### Running the Application

```bash
# Terminal 1: Start the backend
source venv/bin/activate
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start the frontend
cd frontend
npm run dev
```

Access the application at `http://localhost:5173`

---

## 📁 Project Structure

```
medical_assistant/
├── src/
│   ├── api/
│   │   ├── app.py              # FastAPI application
│   │   └── routes.py           # API endpoints
│   ├── crew/
│   │   ├── agents.py           # CrewAI agent definitions
│   │   ├── tasks.py            # Agent task definitions
│   │   ├── tools.py            # Custom agent tools
│   │   └── crew.py             # Crew orchestration
│   ├── extraction/
│   │   ├── file_parser.py      # Universal file parser
│   │   └── llm_extractor.py    # Local FLAN-T5 extractor
│   ├── rag/
│   │   ├── pipeline.py         # RAG orchestration
│   │   ├── embeddings.py       # Bedrock embeddings
│   │   └── vector_store.py     # FAISS operations
│   ├── utils/
│   │   ├── masking.py          # PHI/PII masking
│   │   ├── vault.py            # HashiCorp Vault client
│   │   └── databricks_sync.py  # Databricks sync
│   └── databricks/
│       ├── client.py           # Databricks client
│       └── tables.py           # Table management
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   └── utils/api.js        # API client
│   └── package.json
├── config/
│   ├── settings.py             # Application settings
│   └── extraction.env          # Extraction config
├── scripts/
│   ├── setup_local_llm.sh      # LLM setup script
│   ├── setup_vault.sh          # Vault setup
│   └── deploy.sh               # Deployment script
├── data/
│   ├── raw/                    # Raw input files
│   ├── processed/              # Processed documents
│   └── pii/                    # PII database
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🤖 CrewAI Agents

| Agent | Role | Description |
|-------|------|-------------|
| **Retrieval Agent** | Document Finder | Searches FAISS index for relevant clinical documents |
| **Extraction Agent** | Data Extractor | Extracts structured fields (diagnoses, medications, labs) |
| **Validation Agent** | Quality Checker | Validates completeness and consistency of extracted data |
| **Explanation Agent** | Communicator | Generates human-readable clinical summaries |
| **Routing Agent** | Coordinator | Routes cases to appropriate workflows |

---

## 📄 Supported File Formats

| Format | Extension | Parser |
|--------|-----------|--------|
| PDF | `.pdf` | PyMuPDF + OCR fallback |
| Word | `.docx`, `.doc` | python-docx |
| Excel | `.xlsx`, `.xls` | openpyxl |
| CSV | `.csv` | pandas |
| JSON | `.json` | Native Python |
| XML | `.xml` | ElementTree |
| HL7 v2 | `.hl7` | Custom parser |
| FHIR | `.json` | FHIR R4 parser |
| CDA | `.xml` | CDA R2 parser |
| Images | `.png`, `.jpg` | Tesseract OCR |

---

## 📊 API Endpoints

### Query Endpoints
```
POST /api/query                 # RAG query with Bedrock
POST /api/query/semantic        # Semantic search only
```

### CrewAI Endpoints
```
POST /api/crew/analyze          # Full crew analysis
POST /api/crew/case-brief       # Generate case brief
GET  /api/crew/status/{id}      # Check task status
```

### Extraction Endpoints
```
POST /api/extract/upload        # Upload and parse file
POST /api/extract/process       # Extract with local LLM
GET  /api/extract/models        # List available models
POST /api/extract/databricks    # Sync to Databricks
```

---

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build individually
docker build -t medical-assistant .
docker run -p 8000:8000 -p 5173:5173 medical-assistant
```

---

## 📈 Performance

| Metric | Value |
|--------|-------|
| FAISS Index Size | 238.7 MB |
| Documents Indexed | 55,500 |
| Embedding Dimensions | 1,024 |
| Average Query Time | ~200ms |
| LLM Extraction Time | ~2-5s (CPU) |

---

## 🛣️ Roadmap

- [x] Phase 1: Local RAG Pipeline
- [x] Phase 2: AWS Bedrock Integration
- [x] Phase 3: Databricks Lakehouse
- [x] CrewAI Multi-Agent Workflow
- [x] Local LLM Extraction (FLAN-T5)
- [x] React Frontend
- [ ] MCP Server Implementation
- [ ] Kubernetes Deployment
- [ ] HIPAA Compliance Audit

---

## ⚠️ Disclaimer

This system is designed for **clinical documentation assistance only**. It does NOT:
- Make clinical decisions
- Prescribe medications
- Provide diagnoses

All AI outputs must be reviewed by qualified healthcare professionals.

---

## 👨‍💻 Author

**Kazi Nymul** — [GitHub](https://github.com/kaziNymul)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ for Healthcare AI
</p>
