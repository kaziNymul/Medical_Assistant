# API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

Phase 1 does not include authentication. Add appropriate security for production deployments.

---

## Health Endpoints

### GET /health

Check if the service is healthy.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2025-12-15T10:30:00Z"
}
```

### GET /ready

Check if the service is ready to accept requests.

**Response:**
```json
{
  "ready": true,
  "vector_store_size": 42,
  "document_count": 5
}
```

---

## Document Endpoints

### POST /documents/upload

Upload and process a clinical document.

**Request Body:**
```json
{
  "content": "Clinical note text...",
  "patient_id": "patient_123",
  "source_type": "discharge_summary",
  "document_date": "2025-12-15"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| content | string | Yes | Document text content |
| patient_id | string | Yes | Patient identifier (will be pseudonymized) |
| source_type | enum | No | Type of document (default: "unknown") |
| document_date | string | No | Document date (ISO format) |

**Source Types:**
- `discharge_summary`
- `progress_note`
- `lab_result`
- `radiology_report`
- `prescription`
- `consultation`
- `admission_note`
- `unknown`

**Response:**
```json
{
  "document_id": "DOC-A1B2C3D4E5F6",
  "chunks_created": 3,
  "is_masked": true,
  "pii_items_masked": 5,
  "message": "Document processed successfully. 5 PII items masked."
}
```

### POST /documents/upload-file

Upload a clinical document from a file.

**Request:** Multipart form data
- `file`: Text file (.txt, .md)
- `patient_id`: Patient identifier
- `source_type`: Document type (optional)

**Response:** Same as `/documents/upload`

### GET /documents/stats

Get statistics about indexed documents.

**Response:**
```json
{
  "total_documents": 10,
  "total_chunks": 42,
  "vector_store_path": "./data/vector_store"
}
```

### DELETE /documents/clear

Clear all indexed documents.

**Response:**
```json
{
  "message": "All documents cleared",
  "success": true
}
```

### POST /documents/ingest-sample

Ingest sample clinical data for testing.

**Response:**
```json
{
  "message": "Sample data ingested",
  "chunks_created": 5,
  "total_chunks": 5
}
```

---

## Query Endpoints

### POST /query/extract

Query documents and extract structured clinical data.

**Request Body:**
```json
{
  "query": "What is the patient's HbA1c and medications?",
  "patient_id": null,
  "top_k": 5,
  "include_evidence": true
}
```

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| query | string | Yes | - | Natural language query |
| patient_id | string | No | null | Filter by patient ID |
| top_k | integer | No | 5 | Number of chunks to retrieve (1-20) |
| include_evidence | boolean | No | true | Include source chunks in response |

**Response:**
```json
{
  "query": "What is the patient's HbA1c and medications?",
  "extraction": {
    "primary_diagnosis": "Type 2 Diabetes Mellitus",
    "latest_hba1c": "8.5%",
    "hba1c_trend": "improving",
    "medications": ["Metformin", "Glipizide", "Lisinopril"],
    "smoking_status": "former_smoker",
    "complications": ["Neuropathy"],
    "data_completeness": "complete",
    "confidence_score": 0.87,
    "evidence": [
      {
        "field": "latest_hba1c",
        "quote": "HbA1c: 8.5%",
        "source_type": "discharge_summary",
        "date": "2025-12-15",
        "confidence": 0.95
      }
    ],
    "clinical_explanation": "Primary diagnosis: Type 2 Diabetes Mellitus. Latest HbA1c: 8.5% (trend: improving). Current medications: Metformin, Glipizide, Lisinopril. Smoking status: former smoker.",
    "pii_detected": false,
    "processed_at": "2025-12-15T10:30:00Z",
    "model_version": "phase1-local"
  },
  "retrieved_chunks": [...],
  "processing_time_ms": 245.6
}
```

### POST /query/search

Search for relevant document chunks without extraction.

**Query Parameters:**
- `query` (string, required): Search query
- `top_k` (integer, optional): Number of results (default: 5)
- `patient_id` (string, optional): Filter by patient

**Response:**
```json
{
  "query": "diabetes medications",
  "results": [
    {
      "chunk_id": "DOC-123-C0001",
      "document_id": "DOC-123",
      "content": "Patient on Metformin 1000mg...",
      "score": 0.89,
      "source_type": "progress_note"
    }
  ],
  "total": 5
}
```

---

## Data Models

### ClinicalExtraction

The main output format for clinical extractions:

```json
{
  "primary_diagnosis": "string | null",
  "latest_hba1c": "string | null",
  "hba1c_trend": "improving | stable | worsening | unknown | null",
  "medications": ["string"],
  "smoking_status": "current_smoker | former_smoker | never_smoked | unknown | null",
  "complications": ["string"],
  "data_completeness": "complete | partial | missing",
  "confidence_score": 0.0-1.0,
  "evidence": [Evidence],
  "clinical_explanation": "string | null",
  "pii_detected": false,
  "processed_at": "datetime",
  "model_version": "string"
}
```

### Evidence

Supporting evidence for extracted fields:

```json
{
  "field": "string",
  "quote": "string",
  "source_type": "string",
  "date": "string | null",
  "chunk_id": "string | null",
  "confidence": 0.0-1.0
}
```

---

## Error Responses

### 400 Bad Request

Invalid request parameters.

```json
{
  "detail": "Invalid source_type value"
}
```

### 500 Internal Server Error

Server-side error.

```json
{
  "detail": "Error message description"
}
```

---

## Rate Limits

Phase 1 has no rate limits. Configure appropriate limits for production.

## Versioning

API version: 0.1.0

Future versions will maintain backward compatibility where possible.
