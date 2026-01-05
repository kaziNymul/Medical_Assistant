import { useState, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  Upload, 
  Loader2, 
  FileText, 
  CheckCircle,
  AlertCircle,
  Brain,
  Database,
  Shield,
  ShieldOff,
  Eye,
  EyeOff,
  File,
  X,
  Cpu,
  ChevronDown,
  ChevronUp,
  RefreshCw
} from 'lucide-react'
import { 
  intelligentExtract, 
  intelligentExtractText, 
  getExtractionModels, 
  getSupportedFormats,
  getExtractionSchema
} from '../utils/api'

// File Drop Zone Component for any file type
function UniversalFileDropZone({ onFileDrop, disabled, supportedFormats }) {
  const [isDragging, setIsDragging] = useState(false)
  
  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])
  
  const handleDragIn = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true)
    }
  }, [])
  
  const handleDragOut = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])
  
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    
    if (disabled) return
    
    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      onFileDrop(files[0]) // Single file for extraction
    }
  }, [onFileDrop, disabled])
  
  return (
    <div
      onDragEnter={handleDragIn}
      onDragLeave={handleDragOut}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      className={`
        border-2 border-dashed rounded-lg p-8 text-center transition-all
        ${isDragging 
          ? 'border-purple-500 bg-purple-50' 
          : 'border-gray-300 hover:border-purple-400'
        }
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <Brain className={`w-12 h-12 mx-auto mb-3 ${isDragging ? 'text-purple-500' : 'text-gray-400'}`} />
      <p className="text-gray-700 font-medium text-lg">
        {isDragging ? 'Drop file here...' : 'Drag & drop ANY file'}
      </p>
      <p className="text-sm text-gray-500 mt-2">
        PDF, Word, Excel, CSV, Images, HL7, FHIR, and more
      </p>
      <p className="text-xs text-purple-600 mt-1">
        Local AI will automatically extract clinical data
      </p>
      <div className="mt-4">
        <label className={`
          inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg
          text-sm font-medium hover:bg-purple-700 transition-colors
          ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
        `}>
          <input
            type="file"
            onChange={(e) => e.target.files?.[0] && onFileDrop(e.target.files[0])}
            disabled={disabled}
            className="hidden"
          />
          Select File
        </label>
      </div>
    </div>
  )
}

// Collapsible JSON viewer
function JsonViewer({ data, title, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  
  if (!data) return null
  
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100"
      >
        <span className="font-medium text-gray-700">{title}</span>
        {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {isOpen && (
        <pre className="p-4 text-xs bg-gray-900 text-green-400 overflow-x-auto max-h-96">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

// Clinical field display
function ClinicalField({ label, value, isMasked }) {
  if (!value || value === 'null' || value === 'None') return null
  
  const isMaskedValue = typeof value === 'string' && (
    value.includes('[NAME_') || 
    value.includes('[DATE_') || 
    value.includes('[SSN_') ||
    value.includes('[PHONE_') ||
    value.includes('[EMAIL_')
  )
  
  return (
    <div className="flex justify-between py-2 border-b border-gray-100">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-sm font-medium ${isMaskedValue ? 'text-orange-600 bg-orange-50 px-2 rounded' : 'text-gray-900'}`}>
        {value}
      </span>
    </div>
  )
}

// Extraction results display
function ExtractionResults({ data, showMasked }) {
  const displayData = showMasked ? data.masked : data.unmasked
  
  if (!displayData) return null
  
  return (
    <div className="space-y-6">
      {/* Patient Demographics */}
      {(displayData.patient_name || displayData.date_of_birth || displayData.gender) && (
        <div className="card">
          <h4 className="font-semibold text-gray-800 mb-3 flex items-center">
            <Shield className="w-4 h-4 mr-2 text-purple-500" />
            Patient Demographics
          </h4>
          <div className="space-y-1">
            <ClinicalField label="Name" value={displayData.patient_name} />
            <ClinicalField label="Date of Birth" value={displayData.date_of_birth} />
            <ClinicalField label="Gender" value={displayData.gender} />
            <ClinicalField label="Age" value={displayData.age} />
            <ClinicalField label="MRN" value={displayData.mrn} />
            <ClinicalField label="SSN" value={displayData.ssn} />
            <ClinicalField label="Phone" value={displayData.phone} />
            <ClinicalField label="Email" value={displayData.email} />
            <ClinicalField label="Address" value={displayData.address} />
          </div>
        </div>
      )}
      
      {/* Diagnoses */}
      {displayData.diagnoses?.length > 0 && (
        <div className="card">
          <h4 className="font-semibold text-gray-800 mb-3">Diagnoses</h4>
          <div className="space-y-2">
            {displayData.diagnoses.map((dx, i) => (
              <div key={i} className="p-3 bg-red-50 rounded-lg">
                <p className="font-medium text-red-800">{dx.description || dx.code}</p>
                {dx.code && <p className="text-sm text-red-600">Code: {dx.code}</p>}
                {dx.type && <p className="text-xs text-red-500">Type: {dx.type}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Medications */}
      {displayData.medications?.length > 0 && (
        <div className="card">
          <h4 className="font-semibold text-gray-800 mb-3">Medications</h4>
          <div className="space-y-2">
            {displayData.medications.map((med, i) => (
              <div key={i} className="p-3 bg-blue-50 rounded-lg">
                <p className="font-medium text-blue-800">{med.name}</p>
                <p className="text-sm text-blue-600">
                  {[med.dose, med.frequency, med.route].filter(Boolean).join(' • ')}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Lab Results */}
      {displayData.lab_results?.length > 0 && (
        <div className="card">
          <h4 className="font-semibold text-gray-800 mb-3">Lab Results</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">Test</th>
                  <th className="px-3 py-2 text-left">Value</th>
                  <th className="px-3 py-2 text-left">Unit</th>
                  <th className="px-3 py-2 text-left">Reference</th>
                </tr>
              </thead>
              <tbody>
                {displayData.lab_results.map((lab, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-3 py-2 font-medium">{lab.test}</td>
                    <td className="px-3 py-2">{lab.value}</td>
                    <td className="px-3 py-2 text-gray-500">{lab.unit}</td>
                    <td className="px-3 py-2 text-gray-500">{lab.reference_range}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      
      {/* Vital Signs */}
      {displayData.vital_signs && Object.keys(displayData.vital_signs).length > 0 && (
        <div className="card">
          <h4 className="font-semibold text-gray-800 mb-3">Vital Signs</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(displayData.vital_signs).map(([key, value]) => (
              value && (
                <div key={key} className="p-3 bg-green-50 rounded-lg text-center">
                  <p className="text-xs text-green-600 uppercase">{key.replace('_', ' ')}</p>
                  <p className="font-bold text-green-800">{value}</p>
                </div>
              )
            ))}
          </div>
        </div>
      )}
      
      {/* Assessment & Plan */}
      {(displayData.assessment || displayData.plan) && (
        <div className="card">
          <h4 className="font-semibold text-gray-800 mb-3">Assessment & Plan</h4>
          {displayData.chief_complaint && (
            <div className="mb-3">
              <p className="text-xs text-gray-500 uppercase">Chief Complaint</p>
              <p className="text-gray-800">{displayData.chief_complaint}</p>
            </div>
          )}
          {displayData.assessment && (
            <div className="mb-3">
              <p className="text-xs text-gray-500 uppercase">Assessment</p>
              <p className="text-gray-800">{displayData.assessment}</p>
            </div>
          )}
          {displayData.plan && (
            <div>
              <p className="text-xs text-gray-500 uppercase">Plan</p>
              <p className="text-gray-800">{displayData.plan}</p>
            </div>
          )}
        </div>
      )}
      
      {/* Raw JSON */}
      <JsonViewer data={displayData} title="View Raw JSON" />
    </div>
  )
}

export default function IntelligentExtraction() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [textInput, setTextInput] = useState('')
  const [patientId, setPatientId] = useState('')
  const [inputMode, setInputMode] = useState('file') // 'file' or 'text'
  const [syncToDatabricks, setSyncToDatabricks] = useState(true)
  const [selectedModel, setSelectedModel] = useState('')
  const [showMasked, setShowMasked] = useState(true)
  const [extractionResult, setExtractionResult] = useState(null)
  
  // Fetch available models
  const { data: modelsData } = useQuery({
    queryKey: ['extractionModels'],
    queryFn: () => getExtractionModels().then(r => r.data),
  })
  
  // Fetch supported formats
  const { data: formatsData } = useQuery({
    queryKey: ['supportedFormats'],
    queryFn: () => getSupportedFormats().then(r => r.data),
  })
  
  // File extraction mutation
  const extractFileMutation = useMutation({
    mutationFn: () => intelligentExtract(
      selectedFile, 
      patientId || null, 
      syncToDatabricks, 
      selectedModel || null
    ),
    onSuccess: (response) => {
      setExtractionResult(response.data)
    },
  })
  
  // Text extraction mutation
  const extractTextMutation = useMutation({
    mutationFn: () => intelligentExtractText(
      textInput,
      patientId || null,
      syncToDatabricks,
      selectedModel || null
    ),
    onSuccess: (response) => {
      setExtractionResult(response.data)
    },
  })
  
  const isExtracting = extractFileMutation.isPending || extractTextMutation.isPending
  
  const handleExtract = () => {
    setExtractionResult(null)
    if (inputMode === 'file' && selectedFile) {
      extractFileMutation.mutate()
    } else if (inputMode === 'text' && textInput.trim()) {
      extractTextMutation.mutate()
    }
  }
  
  const handleReset = () => {
    setSelectedFile(null)
    setTextInput('')
    setPatientId('')
    setExtractionResult(null)
    extractFileMutation.reset()
    extractTextMutation.reset()
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-purple-100 rounded-lg">
            <Brain className="w-6 h-6 text-purple-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Intelligent Extraction</h2>
            <p className="text-gray-500">
              Upload any file • Local AI extracts clinical data • Masked & Unmasked to Databricks
            </p>
          </div>
        </div>
      </div>
      
      {/* Feature Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <Cpu className="w-8 h-8 text-purple-600 mb-2" />
          <h3 className="font-semibold text-purple-900">Local LLM Processing</h3>
          <p className="text-sm text-purple-700 mt-1">
            Uses HuggingFace models locally. No data leaves your infrastructure.
          </p>
        </div>
        <div className="card bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <FileText className="w-8 h-8 text-blue-600 mb-2" />
          <h3 className="font-semibold text-blue-900">Any File Format</h3>
          <p className="text-sm text-blue-700 mt-1">
            PDF, Word, Excel, CSV, HL7, FHIR, images (OCR), and more.
          </p>
        </div>
        <div className="card bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <Database className="w-8 h-8 text-green-600 mb-2" />
          <h3 className="font-semibold text-green-900">Dual Storage</h3>
          <p className="text-sm text-green-700 mt-1">
            Stores both masked (de-identified) and unmasked versions in Databricks.
          </p>
        </div>
      </div>
      
      {/* Main Form */}
      <div className="card">
        {/* Input Mode Toggle */}
        <div className="flex space-x-2 mb-6">
          <button
            onClick={() => setInputMode('file')}
            className={`flex-1 py-3 px-4 rounded-lg border-2 transition-all ${
              inputMode === 'file'
                ? 'border-purple-500 bg-purple-50 text-purple-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <Upload className="w-5 h-5 inline mr-2" />
            Upload File
          </button>
          <button
            onClick={() => setInputMode('text')}
            className={`flex-1 py-3 px-4 rounded-lg border-2 transition-all ${
              inputMode === 'text'
                ? 'border-purple-500 bg-purple-50 text-purple-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <FileText className="w-5 h-5 inline mr-2" />
            Paste Text
          </button>
        </div>
        
        {/* File Input */}
        {inputMode === 'file' && (
          <div className="mb-6">
            {!selectedFile ? (
              <UniversalFileDropZone 
                onFileDrop={setSelectedFile}
                disabled={isExtracting}
                supportedFormats={formatsData}
              />
            ) : (
              <div className="p-4 bg-purple-50 rounded-lg flex items-center justify-between">
                <div className="flex items-center">
                  <File className="w-8 h-8 text-purple-600 mr-3" />
                  <div>
                    <p className="font-medium text-purple-900">{selectedFile.name}</p>
                    <p className="text-sm text-purple-600">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedFile(null)}
                  className="p-2 hover:bg-purple-100 rounded-lg"
                >
                  <X className="w-5 h-5 text-purple-600" />
                </button>
              </div>
            )}
          </div>
        )}
        
        {/* Text Input */}
        {inputMode === 'text' && (
          <div className="mb-6">
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Paste clinical note, lab report, discharge summary, or any medical text..."
              className="input-field min-h-[200px] font-mono text-sm"
              rows={10}
            />
          </div>
        )}
        
        {/* Options */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Patient ID (optional)
            </label>
            <input
              type="text"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              placeholder="e.g., PT-12345"
              className="input-field"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Extraction Model
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="input-field"
            >
              <option value="">Default (FLAN-T5 Base)</option>
              {modelsData?.available_models?.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.size})
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Databricks Sync
            </label>
            <button
              onClick={() => setSyncToDatabricks(!syncToDatabricks)}
              className={`w-full flex items-center justify-center py-2 px-4 rounded-lg border transition-all ${
                syncToDatabricks
                  ? 'border-green-500 bg-green-50 text-green-700'
                  : 'border-gray-300 bg-gray-50 text-gray-600'
              }`}
            >
              <Database className="w-4 h-4 mr-2" />
              {syncToDatabricks ? 'Enabled' : 'Disabled'}
            </button>
          </div>
        </div>
        
        {/* Action Buttons */}
        <div className="flex space-x-3">
          <button
            onClick={handleExtract}
            disabled={
              (inputMode === 'file' && !selectedFile) ||
              (inputMode === 'text' && !textInput.trim()) ||
              isExtracting
            }
            className="btn-primary flex items-center bg-purple-600 hover:bg-purple-700"
          >
            {isExtracting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Extracting with AI...
              </>
            ) : (
              <>
                <Brain className="w-4 h-4 mr-2" />
                Extract Clinical Data
              </>
            )}
          </button>
          
          {(extractionResult || selectedFile || textInput) && (
            <button
              onClick={handleReset}
              className="btn-secondary flex items-center"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Reset
            </button>
          )}
        </div>
      </div>
      
      {/* Error Display */}
      {(extractFileMutation.isError || extractTextMutation.isError) && (
        <div className="card bg-red-50 border-red-200">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-500 mr-3 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-800">Extraction Failed</h4>
              <p className="text-sm text-red-600 mt-1">
                {extractFileMutation.error?.response?.data?.detail || 
                 extractTextMutation.error?.response?.data?.detail ||
                 'An error occurred during extraction'}
              </p>
              <p className="text-xs text-red-500 mt-2">
                Make sure transformers and torch are installed: pip install transformers torch
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Results Display */}
      {extractionResult && (
        <div className="space-y-4">
          {/* Success Header */}
          <div className="card bg-green-50 border-green-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <CheckCircle className="w-6 h-6 text-green-500 mr-3" />
                <div>
                  <h4 className="font-semibold text-green-800">Extraction Complete</h4>
                  <p className="text-sm text-green-600">
                    Confidence: {((extractionResult.metadata?.extraction_confidence || 0) * 100).toFixed(0)}%
                    {extractionResult.databricks_sync?.success && ' • Synced to Databricks'}
                  </p>
                </div>
              </div>
              
              {/* Masked/Unmasked Toggle */}
              <button
                onClick={() => setShowMasked(!showMasked)}
                className={`flex items-center px-4 py-2 rounded-lg transition-all ${
                  showMasked 
                    ? 'bg-orange-100 text-orange-700 border border-orange-300'
                    : 'bg-blue-100 text-blue-700 border border-blue-300'
                }`}
              >
                {showMasked ? (
                  <>
                    <ShieldOff className="w-4 h-4 mr-2" />
                    Viewing Masked (Safe)
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4 mr-2" />
                    Viewing Unmasked (PHI)
                  </>
                )}
              </button>
            </div>
          </div>
          
          {/* Databricks Sync Info */}
          {extractionResult.databricks_sync && (
            <div className={`card ${extractionResult.databricks_sync.success ? 'bg-blue-50 border-blue-200' : 'bg-yellow-50 border-yellow-200'}`}>
              <div className="flex items-center">
                <Database className={`w-5 h-5 mr-3 ${extractionResult.databricks_sync.success ? 'text-blue-500' : 'text-yellow-500'}`} />
                <div>
                  <p className={`font-medium ${extractionResult.databricks_sync.success ? 'text-blue-800' : 'text-yellow-800'}`}>
                    {extractionResult.databricks_sync.success ? 'Synced to Databricks' : 'Databricks Sync Skipped'}
                  </p>
                  {extractionResult.databricks_sync.success && (
                    <p className="text-sm text-blue-600">
                      Unmasked: {extractionResult.databricks_sync.unmasked_table} <br />
                      Masked: {extractionResult.databricks_sync.masked_table}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
          
          {/* Extracted Data */}
          <ExtractionResults 
            data={extractionResult.extraction} 
            showMasked={showMasked}
          />
        </div>
      )}
      
      {/* Supported Formats Info */}
      {formatsData && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">Supported File Formats</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Documents</p>
              <p className="text-sm text-gray-700">.pdf, .docx, .txt, .rtf</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Data Files</p>
              <p className="text-sm text-gray-700">.csv, .xlsx, .json, .xml</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Clinical Standards</p>
              <p className="text-sm text-gray-700">.hl7, .fhir, .cda</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase mb-1">Images (OCR)</p>
              <p className="text-sm text-gray-700">.png, .jpg, .tiff</p>
            </div>
          </div>
          <div className="mt-4 flex space-x-2">
            {formatsData.features && Object.entries(formatsData.features).map(([feature, available]) => (
              <span 
                key={feature}
                className={`text-xs px-2 py-1 rounded ${
                  available 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-gray-100 text-gray-500'
                }`}
              >
                {feature}: {available ? '✓' : '✗'}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
