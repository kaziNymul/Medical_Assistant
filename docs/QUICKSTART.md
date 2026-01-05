# Quick Start Guide

## Getting Started with the AI Clinical Documentation Assistant

This guide will help you set up and run the Medical Assistant locally.

## Prerequisites

- Python 3.11 or higher
- pip package manager
- 4GB+ RAM (for embedding model)

## Installation

### 1. Clone and Setup

```bash
cd medical_assistant

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env if needed (defaults work for Phase 1)
```

### 3. Start the Server

```bash
# Run the FastAPI server
python -m src.main

# Or with uvicorn directly
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Quick Test

### 1. Check Health

```bash
curl http://localhost:8000/health
```

### 2. Download Kaggle Data (Bronze Layer)

First, set up Kaggle API credentials:
1. Go to https://www.kaggle.com/settings
2. Scroll to 'API' and click 'Create New Token'
3. Save to ~/.kaggle/kaggle.json

Then download data:
```bash
# List available datasets
python scripts/download_kaggle_data.py --list

# Download healthcare dataset (recommended for first use)
python scripts/download_kaggle_data.py --dataset healthcare
```

### 3. Process Raw Data (Bronze → Silver → Gold)

```bash
# Check data pipeline status
curl http://localhost:8000/data/status

# Process all raw data (applies PII masking)
curl -X POST http://localhost:8000/data/process

# View sample of each layer
curl "http://localhost:8000/data/sample/raw"       # Original data with PII
curl "http://localhost:8000/data/sample/processed" # PII-masked data
curl "http://localhost:8000/data/sample/ai_ready"  # Document format for RAG
```

### 4. Ingest into RAG Vector Store

```bash
# Load processed data into vector store
curl -X POST http://localhost:8000/data/ingest
```

### 5. Upload a Custom Document

```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Patient has Type 2 Diabetes. HbA1c: 7.5%. Taking Metformin 1000mg.",
    "patient_id": "test_001",
    "source_type": "progress_note"
  }'
```

### 6. Extract Clinical Data

```bash
curl -X POST http://localhost:8000/query/extract \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the HbA1c level and current medications?",
    "top_k": 5
  }'
```

## Expected Response

```json
{
  "query": "What is the HbA1c level and current medications?",
  "extraction": {
    "primary_diagnosis": "Type 2 Diabetes",
    "latest_hba1c": "7.5%",
    "medications": ["Metformin"],
    "data_completeness": "partial",
    "confidence_score": 0.85,
    "clinical_explanation": "Primary diagnosis: Type 2 Diabetes. Latest HbA1c: 7.5%. Current medications: Metformin.",
    "pii_detected": false
  },
  "processing_time_ms": 150.5
}
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_masking.py -v
```

## Project Structure

```
medical_assistant/
├── config/              # Configuration
│   └── settings.py      # Pydantic settings
├── data/
│   ├── raw/             # Bronze: Original Kaggle downloads
│   │   └── kaggle/      # Raw CSV files (may contain PII)
│   ├── processed/       # Silver: PII-masked JSON records
│   ├── ai_ready/        # Gold: Document format for RAG
│   └── vector_store/    # FAISS index
├── scripts/
│   └── download_kaggle_data.py  # Kaggle downloader
├── src/
│   ├── agents/          # LangGraph agents
│   ├── api/             # FastAPI application
│   ├── data/            # Data processing pipeline
│   ├── models/          # Pydantic data models
│   ├── rag/             # RAG pipeline
│   └── utils/           # Utilities (masking, logging)
├── tests/               # Test suite
├── .env.example         # Environment template
├── pyproject.toml       # Project configuration
├── requirements.txt     # Dependencies
└── README.md            # Full documentation
```

## Data Pipeline (Bronze → Silver → Gold)

The service implements a Lakehouse-style data architecture:

| Layer | Location | Description |
|-------|----------|-------------|
| **Bronze** | `data/raw/` | Original Kaggle CSV files, may contain PII |
| **Silver** | `data/processed/` | Cleaned and PII-masked JSON records |
| **Gold** | `data/ai_ready/` | Document format ready for RAG indexing |

### Pipeline API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/data/status` | GET | View pipeline status |
| `/data/raw` | GET | List available raw datasets |
| `/data/process` | POST | Run Bronze → Silver → Gold pipeline |
| `/data/ingest` | POST | Load Gold data into vector store |
| `/data/sample/{layer}` | GET | View samples from any layer |

## Key Features

### PII Masking
All text is automatically masked before processing:
- Names → `[PATIENT_NAME]` / `[DOCTOR_NAME]`
- Emails → `[EMAIL]`
- Phone numbers → `[PHONE]`
- SSNs → `[SSN]`
- Addresses → `[ADDRESS]`
- Hospital names → `[HOSPITAL]`

### Clinical Extraction
Extracts structured data including:
- Primary diagnosis
- HbA1c values and trends
- Medications
- Smoking status
- Complications

### Evidence-Based Output
Every extraction includes:
- Source quotes
- Confidence scores
- Data completeness assessment
- Human-readable explanation

## Next Steps

1. **Load your own data**: Upload clinical documents via the API
2. **Phase 2**: Enable AWS Bedrock for Claude-powered extraction
3. **Phase 3**: Integrate Databricks for data engineering

## Troubleshooting

### Model Download Issues
On first run, the embedding model will download. Ensure internet access.

### Memory Errors
The embedding model requires ~1GB RAM. Close other applications if needed.

### Import Errors
Ensure you've activated the virtual environment and installed all dependencies.

## Support

Refer to the main README.md for complete documentation and architecture details.
