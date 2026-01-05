import axios from 'axios'

const API_BASE = '/api'

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Health & Status
export const getHealth = () => api.get('/health')
export const getReady = () => api.get('/ready')

// Data Pipeline
export const getDataStatus = () => api.get('/data/status')
export const getRawDatasets = () => api.get('/data/raw')
export const processData = (dataset = null) => 
  api.post('/data/process', null, { params: dataset ? { dataset } : {} })
export const ingestData = () => api.post('/data/ingest')
export const getSampleData = (layer, limit = 5) => 
  api.get(`/data/sample/${layer}`, { params: { limit } })

// Documents
export const uploadDocument = (content, patientId, sourceType = 'progress_note') =>
  api.post('/documents/upload', { content, patient_id: patientId, source_type: sourceType })
export const getDocumentStats = () => api.get('/documents/stats')
export const clearDocuments = () => api.delete('/documents/clear')

// Query (Original)
export const extractClinicalData = (query, patientId = null, topK = 5, includeEvidence = true) =>
  api.post('/query/extract', { 
    query, 
    patient_id: patientId, 
    top_k: topK,
    include_evidence: includeEvidence 
  })
export const searchDocuments = (query, topK = 5) =>
  api.post('/query/search', null, { params: { query, top_k: topK } })

// Vault Status
export const getVaultStatus = () => api.get('/vault/status')

// ============================================================
// CrewAI Multi-Agent Endpoints
// ============================================================

// Get list of all CrewAI agents
export const getCrewAgents = () => api.get('/crew/agents')

// Get CrewAI system status
export const getCrewStatus = () => api.get('/crew/status')

// Quick extraction (2-agent workflow: Retriever + Extractor)
export const crewQuickExtract = (query, patientId = null) =>
  api.post('/crew/quick-extract', null, { 
    params: { query, patient_id: patientId } 
  })

// Full case brief (5-agent workflow)
export const crewCaseBrief = (query, patientId = null) =>
  api.post('/crew/case-brief', null, { 
    params: { query, patient_id: patientId } 
  })

// ============================================================
// Databricks Endpoints
// ============================================================

// Get Databricks connection status
export const getDatabricksStatus = () => api.get('/databricks/status')

// Get AI logs from Databricks
export const getDatabricksLogs = (limit = 100) => 
  api.get('/databricks/logs', { params: { limit } })

// Get AI metrics from Databricks
export const getDatabricksMetrics = () => api.get('/databricks/metrics')

// Submit feedback for a query
export const submitQueryFeedback = (queryId, rating, feedback = '') =>
  api.post(`/databricks/feedback/${queryId}`, null, { 
    params: { rating, feedback } 
  })

// Sync data to Databricks (requires backend endpoint)
export const syncToDatabricks = () => api.post('/databricks/sync')

// ============================================================
// File Upload Endpoints
// ============================================================

// Upload a file (multipart form)
export const uploadFile = async (file, patientId = null) => {
  const formData = new FormData()
  formData.append('file', file)
  if (patientId) {
    formData.append('patient_id', patientId)
  }
  return api.post('/documents/upload-file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// Bulk upload multiple files
export const uploadFiles = async (files, patientId = null) => {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  if (patientId) {
    formData.append('patient_id', patientId)
  }
  return api.post('/documents/upload-files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// ============================================================
// Intelligent Extraction (Local LLM) Endpoints
// ============================================================

// Get list of available extraction models
export const getExtractionModels = () => api.get('/extract/models')

// Get supported file formats
export const getSupportedFormats = () => api.get('/extract/supported-formats')

// Get clinical data schema
export const getExtractionSchema = () => api.get('/extract/schema')

// Intelligent file extraction with local LLM
export const intelligentExtract = async (file, patientId = null, syncToDatabricks = true, model = null) => {
  const formData = new FormData()
  formData.append('file', file)
  if (patientId) {
    formData.append('patient_id', patientId)
  }
  formData.append('sync_to_databricks', syncToDatabricks)
  if (model) {
    formData.append('model', model)
  }
  return api.post('/extract/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// Extract from text with local LLM
export const intelligentExtractText = async (text, patientId = null, syncToDatabricks = true, model = null) => {
  const formData = new FormData()
  formData.append('text', text)
  if (patientId) {
    formData.append('patient_id', patientId)
  }
  formData.append('sync_to_databricks', syncToDatabricks)
  if (model) {
    formData.append('model', model)
  }
  return api.post('/extract/text', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
