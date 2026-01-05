import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Search, Loader2, FileText, AlertCircle, CheckCircle, X, ChevronDown, ChevronUp, Shield, User, Building2, Stethoscope } from 'lucide-react'
import { extractClinicalData } from '../utils/api'
import clsx from 'clsx'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Document Detail Modal with Original Data Fetch
function DocumentModal({ document, onClose }) {
  const [originalData, setOriginalData] = useState(null)
  const [loadingOriginal, setLoadingOriginal] = useState(false)
  const [error, setError] = useState(null)
  
  useEffect(() => {
    if (!document) return
    
    // Fetch original data from on-prem database using record_id
    const fetchOriginalData = async () => {
      const recordId = document.document_id || document.metadata?._record_id
      if (!recordId) return
      
      setLoadingOriginal(true)
      setError(null)
      
      try {
        const response = await fetch(`${API_URL}/onprem/patient/${recordId}?accessed_by=clinician&access_reason=clinical_review`)
        if (response.ok) {
          const data = await response.json()
          setOriginalData(data)
        } else if (response.status === 404) {
          // Record not found in on-prem DB (might be old data)
          setOriginalData(null)
        } else {
          throw new Error('Failed to fetch original data')
        }
      } catch (err) {
        console.error('Failed to fetch original patient data:', err)
        setError('Could not retrieve original patient data')
      } finally {
        setLoadingOriginal(false)
      }
    }
    
    fetchOriginalData()
  }, [document])
  
  if (!document) return null
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gradient-to-r from-blue-600 to-blue-700">
          <div className="flex items-center">
            <FileText className="w-5 h-5 text-white mr-2" />
            <h3 className="font-semibold text-white">Patient Document Details</h3>
            {originalData && (
              <span className="ml-3 px-2 py-1 bg-green-500 text-white text-xs rounded-full flex items-center">
                <Shield className="w-3 h-3 mr-1" />
                Original Data Loaded
              </span>
            )}
          </div>
          <button 
            onClick={onClose}
            className="p-1 hover:bg-blue-500 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-white" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[65vh]">
          
          {/* Original Patient Data Section (from On-Prem DB) */}
          {loadingOriginal ? (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center">
              <Loader2 className="w-5 h-5 text-blue-600 animate-spin mr-3" />
              <span className="text-blue-700">Loading original patient data from secure database...</span>
            </div>
          ) : originalData ? (
            <div className="mb-6 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-5">
              <div className="flex items-center mb-4">
                <Shield className="w-5 h-5 text-green-600 mr-2" />
                <h4 className="font-semibold text-green-800">Original Patient Information</h4>
                <span className="ml-auto text-xs text-green-600 bg-green-100 px-2 py-1 rounded">
                  From On-Prem Secure Database
                </span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Patient Name */}
                {originalData.patient_name && (
                  <div className="bg-white rounded-lg p-3 border border-green-100">
                    <div className="flex items-center mb-1">
                      <User className="w-4 h-4 text-green-600 mr-2" />
                      <span className="text-xs text-gray-500">Patient Name</span>
                    </div>
                    <p className="font-semibold text-gray-900">{originalData.patient_name}</p>
                  </div>
                )}
                
                {/* Doctor Name */}
                {originalData.doctor_name && (
                  <div className="bg-white rounded-lg p-3 border border-green-100">
                    <div className="flex items-center mb-1">
                      <Stethoscope className="w-4 h-4 text-blue-600 mr-2" />
                      <span className="text-xs text-gray-500">Doctor</span>
                    </div>
                    <p className="font-semibold text-gray-900">{originalData.doctor_name}</p>
                  </div>
                )}
                
                {/* Hospital */}
                {originalData.hospital_name && (
                  <div className="bg-white rounded-lg p-3 border border-green-100">
                    <div className="flex items-center mb-1">
                      <Building2 className="w-4 h-4 text-purple-600 mr-2" />
                      <span className="text-xs text-gray-500">Hospital/Facility</span>
                    </div>
                    <p className="font-semibold text-gray-900">{originalData.hospital_name}</p>
                  </div>
                )}
              </div>
              
              {/* Additional Original Data */}
              {originalData.original_data && Object.keys(originalData.original_data).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs text-green-700 mb-2 font-medium">All Original Fields:</p>
                  <div className="bg-white rounded-lg p-4 border border-green-100 max-h-48 overflow-y-auto">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                      {Object.entries(originalData.original_data)
                        .filter(([key]) => !key.startsWith('_'))
                        .map(([key, value]) => (
                          <div key={key} className="truncate">
                            <span className="text-gray-500">{key}: </span>
                            <span className="text-gray-900 font-medium">{String(value || 'N/A')}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>
              )}
              
              <p className="mt-3 text-xs text-green-600 flex items-center">
                <CheckCircle className="w-3 h-3 mr-1" />
                Access logged for HIPAA compliance
              </p>
            </div>
          ) : error ? (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-amber-700 text-sm">
                <AlertCircle className="w-4 h-4 inline mr-2" />
                {error}
              </p>
            </div>
          ) : null}
          
          {/* Document ID */}
          <div className="mb-4">
            <p className="text-xs text-gray-400 mb-1">Record ID (Links Cloud ↔ On-Prem)</p>
            <p className="text-sm font-mono text-gray-700 bg-gray-100 px-2 py-1 rounded inline-block">
              {document.document_id}
            </p>
          </div>
          
          {/* Source Type */}
          <div className="mb-4">
            <p className="text-xs text-gray-400 mb-1">Source Type</p>
            <span className="badge-info">{document.source_type || 'unknown'}</span>
          </div>
          
          {/* Similarity Score */}
          {document.similarity_score && (
            <div className="mb-4">
              <p className="text-xs text-gray-400 mb-1">Similarity Score</p>
              <div className="flex items-center">
                <div className="w-32 bg-gray-200 rounded-full h-2 mr-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full" 
                    style={{width: `${(document.similarity_score * 100).toFixed(0)}%`}}
                  ></div>
                </div>
                <span className="text-sm font-medium text-gray-700">
                  {(document.similarity_score * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          )}
          
          {/* Full Content (Masked - from Cloud) */}
          <div className="mb-4">
            <p className="text-xs text-gray-400 mb-2">
              Clinical Content <span className="text-amber-500">(AI-Processed Masked Version)</span>
            </p>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                {document.content}
              </p>
            </div>
          </div>
          
          {/* Metadata */}
          {document.metadata && Object.keys(document.metadata).length > 0 && (
            <div>
              <p className="text-xs text-gray-400 mb-2">Metadata (Masked)</p>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(document.metadata)
                    .filter(([key]) => !key.startsWith('_'))
                    .map(([key, value]) => (
                      <div key={key} className="text-sm">
                        <span className="text-gray-500">{key}: </span>
                        <span className="text-gray-800 font-medium">{String(value)}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
          <p className="text-xs text-gray-500">
            {originalData ? (
              <span className="text-green-600">✓ Original data retrieved from secure on-prem database</span>
            ) : (
              <span>Showing masked data from cloud (original not available)</span>
            )}
          </p>
          <button 
            onClick={onClose}
            className="btn-primary"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function ResultCard({ extraction, chunks }) {
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [expandedChunks, setExpandedChunks] = useState({})
  
  if (!extraction) return null
  
  const toggleExpand = (idx) => {
    setExpandedChunks(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }))
  }
  
  return (
    <div className="space-y-6">
      {/* Extraction Results */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Extraction Results</h3>
          <div className="flex items-center space-x-2">
            <span className={clsx(
              'badge',
              extraction.confidence_score >= 0.8 ? 'badge-success' : 
              extraction.confidence_score >= 0.5 ? 'badge-warning' : 'badge-error'
            )}>
              Confidence: {(extraction.confidence_score * 100).toFixed(0)}%
            </span>
            <span className={clsx(
              'badge',
              extraction.data_completeness === 'complete' ? 'badge-success' :
              extraction.data_completeness === 'partial' ? 'badge-warning' : 'badge-error'
            )}>
              {extraction.data_completeness}
            </span>
          </div>
        </div>
        
        {/* Clinical Summary */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <p className="text-blue-800">{extraction.clinical_explanation}</p>
        </div>
        
        {/* Extracted Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {extraction.primary_diagnosis && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Primary Diagnosis</p>
              <p className="font-medium text-gray-900">{extraction.primary_diagnosis}</p>
            </div>
          )}
          
          {extraction.latest_hba1c && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Latest HbA1c</p>
              <p className="font-medium text-gray-900">{extraction.latest_hba1c}</p>
            </div>
          )}
          
          {extraction.medications?.length > 0 && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Medications</p>
              <p className="font-medium text-gray-900">{extraction.medications.join(', ')}</p>
            </div>
          )}
          
          {extraction.smoking_status && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Smoking Status</p>
              <p className="font-medium text-gray-900">{extraction.smoking_status}</p>
            </div>
          )}
        </div>
        
        {/* Evidence */}
        {extraction.evidence?.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Evidence</h4>
            <div className="space-y-2">
              {extraction.evidence.map((ev, idx) => (
                <div key={idx} className="flex items-start p-2 bg-gray-50 rounded text-sm">
                  <CheckCircle className="w-4 h-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="font-medium text-gray-700">{ev.field}: </span>
                    <span className="text-gray-600">"{ev.quote}"</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      
      {/* Document Detail Modal */}
      <DocumentModal 
        document={selectedDoc} 
        onClose={() => setSelectedDoc(null)} 
      />
      
      {/* Retrieved Chunks */}
      {chunks?.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Retrieved Documents ({chunks.length})
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            Click on any document to view full details
          </p>
          <div className="space-y-3">
            {chunks.map((chunk, idx) => (
              <div 
                key={idx} 
                className="border border-gray-200 rounded-lg p-4 hover:border-blue-400 hover:bg-blue-50 cursor-pointer transition-all"
                onClick={() => setSelectedDoc(chunk)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center">
                    <FileText className="w-4 h-4 text-blue-500 mr-2" />
                    <span className="text-sm font-medium text-gray-700">
                      {chunk.document_id?.slice(0, 8)}...
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {chunk.similarity_score && (
                      <span className="text-xs text-gray-500">
                        {(chunk.similarity_score * 100).toFixed(0)}% match
                      </span>
                    )}
                    <span className="badge-info">{chunk.source_type || 'unknown'}</span>
                  </div>
                </div>
                <p className="text-sm text-gray-600 line-clamp-2">{chunk.content}</p>
                <p className="text-xs text-blue-600 mt-2 flex items-center">
                  Click to view full document
                  <ChevronDown className="w-3 h-3 ml-1" />
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function Query() {
  const [query, setQuery] = useState('')
  const [patientId, setPatientId] = useState('')
  
  const mutation = useMutation({
    mutationFn: () => extractClinicalData(query, patientId || null),
  })
  
  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      mutation.mutate()
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Clinical Query</h2>
        <p className="text-gray-500 mt-1">
          Search indexed documents and extract structured clinical data
        </p>
      </div>
      
      {/* Search Form */}
      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Query
              </label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., Find all patients with diabetes and their medications..."
                className="input-field min-h-[100px]"
                rows={3}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Patient ID (optional)
              </label>
              <input
                type="text"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="Filter by patient ID"
                className="input-field"
              />
            </div>
            
            <button
              type="submit"
              disabled={!query.trim() || mutation.isPending}
              className="btn-primary flex items-center"
            >
              {mutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              {mutation.isPending ? 'Searching...' : 'Search & Extract'}
            </button>
          </div>
        </form>
      </div>
      
      {/* Error */}
      {mutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="w-5 h-5 text-red-500 mr-3 mt-0.5" />
          <div>
            <p className="font-medium text-red-800">Query failed</p>
            <p className="text-sm text-red-600">{mutation.error?.message || 'Unknown error'}</p>
          </div>
        </div>
      )}
      
      {/* Results */}
      {mutation.isSuccess && (
        <ResultCard
          extraction={mutation.data.data.extraction}
          chunks={mutation.data.data.retrieved_chunks}
        />
      )}
      
      {/* Example Queries */}
      {!mutation.data && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Example Queries</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              'diabetes medications',
              'patients with hypertension',
              'abnormal test results',
              'heart disease treatment',
            ].map((example) => (
              <button
                key={example}
                onClick={() => setQuery(example)}
                className="text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <p className="text-sm text-gray-600">"{example}"</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
