# Data Directory Structure

This directory follows a Lakehouse-style architecture for data processing.

## Directory Structure

```
data/
├── raw/                  # Bronze: Unprocessed Kaggle downloads
│   └── kaggle/           # Original CSV files from Kaggle
│       ├── healthcare/   # Healthcare dataset with patient records
│       ├── diabetes/     # Diabetes indicators dataset
│       └── heart-failure/# Heart failure clinical records
├── processed/            # Silver: Cleaned and PII-masked data
│   └── *_silver.json     # Masked JSON records
├── ai_ready/             # Gold: Transformed for RAG consumption
│   └── *_gold.json       # Document-structured data
├── vector_store/         # FAISS index and metadata
└── logs/                 # Processing logs and audit trails
```

## Data Flow (Bronze → Silver → Gold)

```
┌─────────────────┐
│  Kaggle API     │
└────────┬────────┘
         ↓
┌─────────────────┐     Download Script
│   data/raw/     │     python scripts/download_kaggle_data.py
│   (BRONZE)      │     
│   • Original    │     
│   • Contains PII│     
│   • CSV format  │     
└────────┬────────┘
         ↓
┌─────────────────┐     Process API
│ data/processed/ │     POST /data/process
│   (SILVER)      │     
│   • PII masked  │     
│   • Validated   │     
│   • JSON format │     
└────────┬────────┘
         ↓
┌─────────────────┐     Transform + Chunk
│ data/ai_ready/  │     
│   (GOLD)        │     
│   • Text docs   │     
│   • RAG-ready   │     
│   • Normalized  │     
└────────┬────────┘
         ↓
┌─────────────────┐     Ingest API
│ vector_store/   │     POST /data/ingest
│   • FAISS index │     
│   • Embeddings  │     
│   • Metadata    │     
└─────────────────┘
```

## Quick Start

### Step 1: Download Raw Data (Bronze)
```bash
# List available datasets
python scripts/download_kaggle_data.py --list

# Download specific dataset
python scripts/download_kaggle_data.py --dataset healthcare

# Download all datasets
python scripts/download_kaggle_data.py --dataset all
```

### Step 2: Process and Mask (Silver)
```bash
# Start the API server
python -m src.main

# Process all raw data (applies PII masking)
curl -X POST http://localhost:8000/data/process

# Check processing status
curl http://localhost:8000/data/status
```

### Step 3: View Samples at Each Layer
```bash
# View raw (Bronze) data - contains PII
curl http://localhost:8000/data/sample/raw

# View processed (Silver) data - PII masked
curl http://localhost:8000/data/sample/processed

# View AI-ready (Gold) data - document format
curl http://localhost:8000/data/sample/ai_ready
```

### Step 4: Ingest into RAG
```bash
# Load Gold data into vector store
curl -X POST http://localhost:8000/data/ingest

# Now query the data
curl -X POST http://localhost:8000/query/extract \
  -H "Content-Type: application/json" \
  -d '{"query": "diabetes medications"}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/data/status` | GET | View pipeline status (raw/processed/ready counts) |
| `/data/raw` | GET | List available raw datasets |
| `/data/process` | POST | Run Bronze → Silver → Gold pipeline |
| `/data/ingest` | POST | Load Gold data into vector store |
| `/data/sample/{layer}` | GET | View sample records from any layer |

## PII Masking

The Silver layer applies comprehensive PII masking:

| PII Type | Example Before | Example After |
|----------|---------------|---------------|
| Email | john.doe@email.com | [EMAIL_1] |
| Phone | 555-123-4567 | [PHONE_1] |
| SSN | 123-45-6789 | [SSN_1] |
| Name | Dr. John Smith | [NAME_1] |
| Hospital | Mayo Clinic | [HOSPITAL_1] |

## Privacy & Compliance Notes

- **Raw data (Bronze)**: May contain synthetic PII patterns from Kaggle
- **Processed data (Silver)**: All PII patterns replaced with placeholders
- **AI-ready data (Gold)**: Only de-identified text used for inference
- **Audit trail**: `_metadata.json` tracks processing timestamps
- **HIPAA-style**: Follows Safe Harbor de-identification approach
