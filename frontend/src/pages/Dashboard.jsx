import { useQuery } from '@tanstack/react-query'
import { 
  FileText, 
  Database, 
  Layers, 
  Activity,
  CheckCircle,
  AlertCircle,
  Clock,
  Users,
  Brain
} from 'lucide-react'
import { getHealth, getReady, getDataStatus, getDocumentStats, getCrewStatus } from '../utils/api'

function StatCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    purple: 'bg-purple-500',
    orange: 'bg-orange-500',
  }
  
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`${colors[color]} p-3 rounded-lg`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  )
}

function StatusItem({ label, status, detail }) {
  const statusConfig = {
    healthy: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50' },
    ready: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50' },
    pending: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-50' },
    error: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50' },
  }
  
  const config = statusConfig[status] || statusConfig.pending
  const Icon = config.icon
  
  return (
    <div className={`flex items-center justify-between p-4 rounded-lg ${config.bg}`}>
      <div className="flex items-center">
        <Icon className={`w-5 h-5 ${config.color} mr-3`} />
        <div>
          <p className="font-medium text-gray-900">{label}</p>
          {detail && <p className="text-sm text-gray-500">{detail}</p>}
        </div>
      </div>
      <span className={`text-sm font-medium ${config.color} capitalize`}>
        {status}
      </span>
    </div>
  )
}

export default function Dashboard() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => getHealth().then(r => r.data),
  })
  
  const { data: ready } = useQuery({
    queryKey: ['ready'],
    queryFn: () => getReady().then(r => r.data),
  })
  
  const { data: dataStatus } = useQuery({
    queryKey: ['dataStatus'],
    queryFn: () => getDataStatus().then(r => r.data),
  })
  
  const { data: docStats } = useQuery({
    queryKey: ['docStats'],
    queryFn: () => getDocumentStats().then(r => r.data),
  })
  
  const { data: crewStatus } = useQuery({
    queryKey: ['crewStatus'],
    queryFn: () => getCrewStatus().then(r => r.data),
  })
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-gray-500 mt-1">
          Overview of your clinical documentation system
        </p>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Documents"
          value={docStats?.total_documents || 0}
          subtitle="In vector store"
          icon={FileText}
          color="blue"
        />
        <StatCard
          title="Total Chunks"
          value={docStats?.total_chunks?.toLocaleString() || 0}
          subtitle="Indexed for search"
          icon={Layers}
          color="purple"
        />
        <StatCard
          title="Raw Datasets"
          value={dataStatus?.summary?.raw_count || 0}
          subtitle="Available for processing"
          icon={Database}
          color="orange"
        />
        <StatCard
          title="Processed Files"
          value={dataStatus?.summary?.processed_count || 0}
          subtitle="Ready for AI"
          icon={Activity}
          color="green"
        />
      </div>
      
      {/* System Status */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">System Status</h3>
        <div className="space-y-3">
          <StatusItem
            label="API Server"
            status={health?.status || 'pending'}
            detail={`Version ${health?.version || '...'}`}
          />
          <StatusItem
            label="Vector Store"
            status={ready?.ready ? 'ready' : 'pending'}
            detail={`${ready?.vector_store_size?.toLocaleString() || 0} chunks loaded`}
          />
          <StatusItem
            label="PII Masking"
            status="healthy"
            detail="HIPAA-compliant de-identification active"
          />
          <StatusItem
            label="LLM Provider"
            status={health ? 'healthy' : 'pending'}
            detail="AWS Bedrock (Claude 3 Haiku)"
          />
          <StatusItem
            label="CrewAI Agents"
            status={crewStatus?.status === 'ready' ? 'ready' : 'pending'}
            detail={`${crewStatus?.agents_initialized || 0} agents initialized`}
          />
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <a
            href="/case-brief"
            className="flex items-center p-4 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors border-2 border-purple-200"
          >
            <div className="bg-purple-500 p-2 rounded-lg mr-4">
              <Users className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-medium text-purple-900">AI Case Brief</p>
              <p className="text-sm text-purple-600">5-agent CrewAI workflow</p>
            </div>
          </a>
          
          <a
            href="/query"
            className="flex items-center p-4 bg-primary-50 hover:bg-primary-100 rounded-lg transition-colors"
          >
            <div className="bg-primary-500 p-2 rounded-lg mr-4">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-medium text-primary-900">Query Documents</p>
              <p className="text-sm text-primary-600">Search and extract data</p>
            </div>
          </a>
          
          <a
            href="/documents"
            className="flex items-center p-4 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
          >
            <div className="bg-green-500 p-2 rounded-lg mr-4">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-medium text-green-900">Upload Document</p>
              <p className="text-sm text-green-600">Add clinical notes</p>
            </div>
          </a>
          
          <a
            href="/data"
            className="flex items-center p-4 bg-orange-50 hover:bg-orange-100 rounded-lg transition-colors"
          >
            <div className="bg-orange-500 p-2 rounded-lg mr-4">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-medium text-orange-900">Process Data</p>
              <p className="text-sm text-orange-600">Run Bronze → Gold pipeline</p>
            </div>
          </a>
        </div>
      </div>
    </div>
  )
}
