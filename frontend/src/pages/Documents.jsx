import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Upload, 
  Loader2, 
  FileText, 
  Trash2, 
  CheckCircle,
  AlertCircle,
  File,
  X
} from 'lucide-react'
import { uploadDocument, uploadFile, getDocumentStats, clearDocuments } from '../utils/api'

// File Drop Zone Component
function FileDropZone({ onFileDrop, disabled }) {
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
      onFileDrop(Array.from(files))
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
          ? 'border-blue-500 bg-blue-50' 
          : 'border-gray-300 hover:border-gray-400'
        }
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <Upload className={`w-10 h-10 mx-auto mb-3 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`} />
      <p className="text-gray-600 font-medium">
        {isDragging ? 'Drop files here...' : 'Drag & drop files here'}
      </p>
      <p className="text-sm text-gray-400 mt-1">
        Supports .txt and .md files
      </p>
      <div className="mt-4">
        <label className={`
          inline-flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg
          text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors
          ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}
        `}>
          <input
            type="file"
            accept=".txt,.md,.text"
            multiple
            onChange={(e) => onFileDrop(Array.from(e.target.files))}
            disabled={disabled}
            className="hidden"
          />
          Or click to browse
        </label>
      </div>
    </div>
  )
}

export default function Documents() {
  const queryClient = useQueryClient()
  const [content, setContent] = useState('')
  const [patientId, setPatientId] = useState('')
  const [sourceType, setSourceType] = useState('progress_note')
  const [uploadMode, setUploadMode] = useState('text') // 'text' or 'file'
  const [selectedFiles, setSelectedFiles] = useState([])
  
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['docStats'],
    queryFn: () => getDocumentStats().then(r => r.data),
  })
  
  const uploadMutation = useMutation({
    mutationFn: () => uploadDocument(content, patientId, sourceType),
    onSuccess: () => {
      queryClient.invalidateQueries(['docStats'])
      setContent('')
      setPatientId('')
    },
  })
  
  const fileUploadMutation = useMutation({
    mutationFn: async () => {
      const results = []
      for (const file of selectedFiles) {
        const result = await uploadFile(file, patientId || null)
        results.push(result)
      }
      return results
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['docStats'])
      setSelectedFiles([])
      setPatientId('')
    },
  })
  
  const clearMutation = useMutation({
    mutationFn: clearDocuments,
    onSuccess: () => {
      queryClient.invalidateQueries(['docStats'])
    },
  })
  
  const handleSubmit = (e) => {
    e.preventDefault()
    if (uploadMode === 'text' && content.trim() && patientId.trim()) {
      uploadMutation.mutate()
    } else if (uploadMode === 'file' && selectedFiles.length > 0) {
      fileUploadMutation.mutate()
    }
  }
  
  const handleFileDrop = (files) => {
    // Filter to allowed extensions
    const allowedFiles = files.filter(f => 
      f.name.endsWith('.txt') || f.name.endsWith('.md') || f.name.endsWith('.text')
    )
    setSelectedFiles(prev => [...prev, ...allowedFiles])
  }
  
  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }
  
  const isUploading = uploadMutation.isPending || fileUploadMutation.isPending
  
  const sourceTypes = [
    { value: 'progress_note', label: 'Progress Note' },
    { value: 'discharge_summary', label: 'Discharge Summary' },
    { value: 'lab_result', label: 'Lab Result' },
    { value: 'radiology_report', label: 'Radiology Report' },
    { value: 'prescription', label: 'Prescription' },
    { value: 'consultation', label: 'Consultation' },
    { value: 'admission_note', label: 'Admission Note' },
  ]
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Documents</h2>
          <p className="text-gray-500 mt-1">
            Upload and manage clinical documents
          </p>
        </div>
        
        <button
          onClick={() => clearMutation.mutate()}
          disabled={clearMutation.isPending || stats?.total_documents === 0}
          className="btn-secondary flex items-center text-red-600 hover:text-red-700"
        >
          {clearMutation.isPending ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4 mr-2" />
          )}
          Clear All
        </button>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center">
            <div className="bg-blue-100 p-3 rounded-lg mr-4">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Documents</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? '...' : stats?.total_documents || 0}
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="bg-purple-100 p-3 rounded-lg mr-4">
              <FileText className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Chunks</p>
              <p className="text-2xl font-bold text-gray-900">
                {statsLoading ? '...' : stats?.total_chunks?.toLocaleString() || 0}
              </p>
            </div>
          </div>
        </div>
        
        <div className="card">
          <div className="flex items-center">
            <div className="bg-green-100 p-3 rounded-lg mr-4">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">PII Masking</p>
              <p className="text-2xl font-bold text-gray-900">Active</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Upload Form */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Document</h3>
        
        {/* Upload Mode Toggle */}
        <div className="flex space-x-2 mb-4">
          <button
            onClick={() => setUploadMode('text')}
            className={`flex-1 py-2 px-4 rounded-lg border transition-all ${
              uploadMode === 'text'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Paste Text
          </button>
          <button
            onClick={() => setUploadMode('file')}
            className={`flex-1 py-2 px-4 rounded-lg border transition-all ${
              uploadMode === 'file'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <Upload className="w-4 h-4 inline mr-2" />
            Upload Files
          </button>
        </div>
        
        {/* Success Message */}
        {(uploadMutation.isSuccess || fileUploadMutation.isSuccess) && (
          <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-4 flex items-start">
            <CheckCircle className="w-5 h-5 text-green-500 mr-3 mt-0.5" />
            <div>
              <p className="font-medium text-green-800">Document uploaded successfully</p>
              <p className="text-sm text-green-600">
                {uploadMutation.data?.data?.chunks_created || fileUploadMutation.data?.length || 0} chunks created, 
                PII automatically masked
              </p>
            </div>
          </div>
        )}
        
        {/* Error Message */}
        {(uploadMutation.isError || fileUploadMutation.isError) && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
            <AlertCircle className="w-5 h-5 text-red-500 mr-3 mt-0.5" />
            <div>
              <p className="font-medium text-red-800">Upload failed</p>
              <p className="text-sm text-red-600">
                {uploadMutation.error?.message || fileUploadMutation.error?.message}
              </p>
            </div>
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Common Fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Patient ID {uploadMode === 'text' && <span className="text-red-500">*</span>}
              </label>
              <input
                type="text"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="e.g., PT-12345"
                className="input-field"
                required={uploadMode === 'text'}
              />
            </div>
            
            {uploadMode === 'text' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Source Type
                </label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="input-field"
                >
                  {sourceTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          
          {/* Text Mode: Textarea */}
          {uploadMode === 'text' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Clinical Content <span className="text-red-500">*</span>
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Paste clinical note content here. PII will be automatically masked..."
                className="input-field min-h-[200px]"
                rows={8}
                required
              />
              <p className="mt-1 text-sm text-gray-500">
                Names, emails, phone numbers, SSNs, and other PII will be automatically de-identified.
              </p>
            </div>
          )}
          
          {/* File Mode: Drag & Drop */}
          {uploadMode === 'file' && (
            <div>
              <FileDropZone onFileDrop={handleFileDrop} disabled={isUploading} />
              
              {/* Selected Files List */}
              {selectedFiles.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-sm font-medium text-gray-700">
                    Selected Files ({selectedFiles.length})
                  </p>
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center">
                        <File className="w-4 h-4 text-gray-400 mr-2" />
                        <span className="text-sm text-gray-700">{file.name}</span>
                        <span className="text-xs text-gray-400 ml-2">
                          ({(file.size / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(idx)}
                        className="p-1 hover:bg-gray-200 rounded"
                      >
                        <X className="w-4 h-4 text-gray-500" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          <button
            type="submit"
            disabled={
              (uploadMode === 'text' && (!content.trim() || !patientId.trim())) ||
              (uploadMode === 'file' && selectedFiles.length === 0) ||
              isUploading
            }
            className="btn-primary flex items-center"
          >
            {isUploading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Upload className="w-4 h-4 mr-2" />
            )}
            {isUploading ? 'Uploading...' : uploadMode === 'text' ? 'Upload Document' : `Upload ${selectedFiles.length} File(s)`}
          </button>
        </form>
      </div>
      
      {/* Sample Document */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Sample Document</h3>
        <p className="text-sm text-gray-500 mb-3">
          Click to use this sample clinical note:
        </p>
        <button
          onClick={() => {
            setPatientId('PT-DEMO-001')
            setContent(`Patient: John Smith
DOB: 01/15/1965
Email: john.smith@email.com
Phone: 555-123-4567

Chief Complaint: Follow-up for Type 2 Diabetes management

History of Present Illness:
62-year-old male with Type 2 Diabetes diagnosed 5 years ago. Currently on Metformin 1000mg twice daily. Reports good compliance with medications. Denies hypoglycemic episodes.

Lab Results:
- HbA1c: 7.2% (improved from 7.8% three months ago)
- Fasting glucose: 126 mg/dL
- Creatinine: 1.1 mg/dL

Physical Exam:
- BP: 128/82 mmHg
- Weight: 185 lbs (down from 192 lbs)
- BMI: 27.8

Assessment:
1. Type 2 Diabetes - improved control
2. Hypertension - well controlled
3. Obesity - improving with lifestyle changes

Plan:
1. Continue Metformin 1000mg BID
2. Maintain current diet and exercise regimen
3. Follow-up in 3 months with repeat HbA1c

Dr. Sarah Johnson, MD
Internal Medicine
Mayo Clinic`)
          }}
          className="text-left p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors w-full"
        >
          <p className="text-sm text-gray-600">
            Clinical progress note with patient information, lab results, and treatment plan
          </p>
        </button>
      </div>
    </div>
  )
}
