import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Database, 
  Loader2, 
  Play, 
  RefreshCw,
  CheckCircle,
  Clock,
  AlertCircle,
  Layers,
  ArrowRight
} from 'lucide-react'
import { getDataStatus, processData, ingestData, getSampleData } from '../utils/api'
import clsx from 'clsx'

function PipelineStep({ number, title, description, status, count }) {
  const statusConfig = {
    complete: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-100' },
    pending: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-100' },
    empty: { icon: AlertCircle, color: 'text-gray-400', bg: 'bg-gray-100' },
  }
  
  const config = statusConfig[status] || statusConfig.empty
  const Icon = config.icon
  
  return (
    <div className="flex items-start">
      <div className={clsx('flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center', config.bg)}>
        <span className={clsx('font-bold', config.color)}>{number}</span>
      </div>
      <div className="ml-4 flex-1">
        <div className="flex items-center justify-between">
          <h4 className="font-medium text-gray-900">{title}</h4>
          <div className="flex items-center">
            <Icon className={clsx('w-4 h-4 mr-1', config.color)} />
            <span className={clsx('text-sm', config.color)}>
              {count !== undefined ? `${count} files` : status}
            </span>
          </div>
        </div>
        <p className="text-sm text-gray-500 mt-1">{description}</p>
      </div>
    </div>
  )
}

function SampleDataViewer({ layer }) {
  const { data, isLoading } = useQuery({
    queryKey: ['sampleData', layer],
    queryFn: () => getSampleData(layer, 3).then(r => r.data),
    enabled: !!layer,
  })
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    )
  }
  
  if (!data?.samples?.length) {
    return (
      <div className="text-center py-8 text-gray-500">
        No data in {layer} layer
      </div>
    )
  }
  
  return (
    <div className="space-y-3">
      {data.samples.map((sample, idx) => (
        <div key={idx} className="bg-gray-50 rounded-lg p-4 overflow-auto">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-gray-500">{sample.source}</span>
          </div>
          <pre className="text-xs text-gray-700 whitespace-pre-wrap">
            {JSON.stringify(sample.data, null, 2).slice(0, 500)}
            {JSON.stringify(sample.data).length > 500 && '...'}
          </pre>
        </div>
      ))}
    </div>
  )
}

export default function DataPipeline() {
  const queryClient = useQueryClient()
  const [activeLayer, setActiveLayer] = useState('raw')
  
  const { data: status, isLoading } = useQuery({
    queryKey: ['dataStatus'],
    queryFn: () => getDataStatus().then(r => r.data),
  })
  
  const processMutation = useMutation({
    mutationFn: () => processData(),
    onSuccess: () => {
      queryClient.invalidateQueries(['dataStatus'])
    },
  })
  
  const ingestMutation = useMutation({
    mutationFn: ingestData,
    onSuccess: () => {
      queryClient.invalidateQueries(['dataStatus', 'docStats', 'ready'])
    },
  })
  
  const layers = [
    { id: 'raw', name: 'Bronze (Raw)', color: 'orange' },
    { id: 'processed', name: 'Silver (Processed)', color: 'gray' },
    { id: 'ai_ready', name: 'Gold (AI Ready)', color: 'yellow' },
  ]
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Data Pipeline</h2>
          <p className="text-gray-500 mt-1">
            Bronze → Silver → Gold data processing
          </p>
        </div>
        
        <button
          onClick={() => queryClient.invalidateQueries(['dataStatus'])}
          className="btn-secondary flex items-center"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>
      
      {/* Pipeline Visualization */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-6">Pipeline Status</h3>
        
        <div className="flex items-center justify-between mb-8">
          {/* Bronze */}
          <div className="flex-1 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-orange-100 mb-2">
              <Database className="w-8 h-8 text-orange-600" />
            </div>
            <p className="font-medium text-gray-900">Bronze</p>
            <p className="text-sm text-gray-500">Raw Data</p>
            <p className="text-lg font-bold text-orange-600 mt-1">
              {status?.summary?.raw_count || 0}
            </p>
          </div>
          
          <ArrowRight className="w-6 h-6 text-gray-300 flex-shrink-0" />
          
          {/* Silver */}
          <div className="flex-1 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-2">
              <Layers className="w-8 h-8 text-gray-600" />
            </div>
            <p className="font-medium text-gray-900">Silver</p>
            <p className="text-sm text-gray-500">Masked</p>
            <p className="text-lg font-bold text-gray-600 mt-1">
              {status?.summary?.processed_count || 0}
            </p>
          </div>
          
          <ArrowRight className="w-6 h-6 text-gray-300 flex-shrink-0" />
          
          {/* Gold */}
          <div className="flex-1 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-yellow-100 mb-2">
              <Database className="w-8 h-8 text-yellow-600" />
            </div>
            <p className="font-medium text-gray-900">Gold</p>
            <p className="text-sm text-gray-500">AI Ready</p>
            <p className="text-lg font-bold text-yellow-600 mt-1">
              {status?.summary?.ai_ready_count || 0}
            </p>
          </div>
        </div>
        
        {/* Action Buttons */}
        <div className="flex space-x-4">
          <button
            onClick={() => processMutation.mutate()}
            disabled={processMutation.isPending || status?.summary?.raw_count === 0}
            className="btn-primary flex items-center flex-1 justify-center"
          >
            {processMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            {processMutation.isPending ? 'Processing...' : 'Process Raw Data'}
          </button>
          
          <button
            onClick={() => ingestMutation.mutate()}
            disabled={ingestMutation.isPending || status?.summary?.ai_ready_count === 0}
            className="btn-secondary flex items-center flex-1 justify-center"
          >
            {ingestMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Database className="w-4 h-4 mr-2" />
            )}
            {ingestMutation.isPending ? 'Ingesting...' : 'Ingest to Vector Store'}
          </button>
        </div>
        
        {/* Success Messages */}
        {processMutation.isSuccess && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center">
              <CheckCircle className="w-5 h-5 text-green-500 mr-2" />
              <span className="text-green-800">
                Processed {processMutation.data?.data?.datasets_processed || 0} datasets
              </span>
            </div>
          </div>
        )}
        
        {ingestMutation.isSuccess && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center">
              <CheckCircle className="w-5 h-5 text-green-500 mr-2" />
              <span className="text-green-800">
                Ingested {ingestMutation.data?.data?.chunks_created?.toLocaleString() || 0} chunks into vector store
              </span>
            </div>
          </div>
        )}
      </div>
      
      {/* Raw Datasets */}
      {status?.raw_datasets?.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Raw Datasets</h3>
          <div className="space-y-3">
            {status.raw_datasets.map((dataset, idx) => (
              <div key={idx} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">{dataset.dataset_key}</p>
                  <p className="text-sm text-gray-500">{dataset.description}</p>
                </div>
                <div className="flex items-center space-x-2">
                  {dataset.contains_pii && (
                    <span className="badge-warning">Contains PII</span>
                  )}
                  <span className={dataset.processed ? 'badge-success' : 'badge-info'}>
                    {dataset.processed ? 'Processed' : 'Not processed'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Sample Data Viewer */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Sample Data</h3>
        
        {/* Layer Tabs */}
        <div className="flex space-x-2 mb-4">
          {layers.map((layer) => (
            <button
              key={layer.id}
              onClick={() => setActiveLayer(layer.id)}
              className={clsx(
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                activeLayer === layer.id
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              {layer.name}
            </button>
          ))}
        </div>
        
        <SampleDataViewer layer={activeLayer} />
      </div>
    </div>
  )
}
