import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { 
  Users, 
  Loader2, 
  FileText, 
  AlertCircle, 
  CheckCircle, 
  Search,
  Brain,
  Shield,
  Activity,
  ClipboardList,
  AlertTriangle,
  Bot,
  Zap,
  Clock
} from 'lucide-react'
import { crewQuickExtract, crewCaseBrief, getCrewStatus, getCrewAgents } from '../utils/api'
import clsx from 'clsx'

// Agent Card Component
function AgentCard({ agent, isActive = false }) {
  const iconMap = {
    'Medical Record Retriever': Search,
    'Clinical Information Extractor': ClipboardList,
    'Risk & Trend Analyst': AlertTriangle,
    'Clinical Gaps Finder': AlertCircle,
    'Case Brief Writer': FileText,
  }
  
  const Icon = iconMap[agent.name] || Bot
  
  return (
    <div className={clsx(
      'p-3 rounded-lg border transition-all',
      isActive 
        ? 'bg-blue-50 border-blue-300 shadow-md' 
        : 'bg-gray-50 border-gray-200'
    )}>
      <div className="flex items-center">
        <div className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center mr-3',
          isActive ? 'bg-blue-500 text-white' : 'bg-gray-300 text-gray-600'
        )}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className={clsx(
            'text-sm font-medium truncate',
            isActive ? 'text-blue-800' : 'text-gray-700'
          )}>
            {agent.name}
          </p>
          <p className="text-xs text-gray-500 truncate">{agent.role}</p>
        </div>
        {isActive && (
          <Loader2 className="w-4 h-4 text-blue-500 animate-spin ml-2" />
        )}
      </div>
    </div>
  )
}

// Results Display Component
function CaseBriefResults({ data, isQuickMode }) {
  if (!data) return null
  
  const parseResult = (result) => {
    if (typeof result === 'string') {
      try {
        return JSON.parse(result)
      } catch {
        return { raw: result }
      }
    }
    return result
  }
  
  const parsed = isQuickMode 
    ? parseResult(data.extraction)
    : parseResult(data.case_brief)

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      <div className={clsx(
        'p-4 rounded-lg flex items-center',
        data.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
      )}>
        {data.success ? (
          <CheckCircle className="w-5 h-5 text-green-500 mr-3" />
        ) : (
          <AlertCircle className="w-5 h-5 text-red-500 mr-3" />
        )}
        <div className="flex-1">
          <p className={clsx('font-medium', data.success ? 'text-green-800' : 'text-red-800')}>
            {data.success ? 'Analysis Complete' : 'Analysis Failed'}
          </p>
          <p className="text-sm text-gray-600">
            Processed in {data.processing_time_seconds?.toFixed(1) || '?'} seconds
          </p>
        </div>
        {data.agents_used && (
          <span className="badge-info">
            {data.agents_used.length} agents used
          </span>
        )}
      </div>

      {/* Main Results Card */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <Brain className="w-5 h-5 text-purple-500 mr-2" />
            {isQuickMode ? 'Quick Extraction Results' : 'Full Case Briefing'}
          </h3>
        </div>

        {/* Parsed Results */}
        {parsed.raw ? (
          <div className="bg-gray-50 rounded-lg p-4">
            <pre className="text-sm text-gray-800 whitespace-pre-wrap font-mono">
              {parsed.raw}
            </pre>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Chief Complaint */}
            {parsed.chief_complaint && (
              <div className="p-3 bg-blue-50 rounded-lg">
                <p className="text-xs text-blue-600 mb-1">Chief Complaint</p>
                <p className="font-medium text-blue-900">{parsed.chief_complaint}</p>
              </div>
            )}

            {/* Conditions */}
            {parsed.conditions?.length > 0 && (
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-2">Active Conditions</p>
                <div className="flex flex-wrap gap-2">
                  {parsed.conditions.map((c, i) => (
                    <span key={i} className="badge-info">{c}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Medications */}
            {parsed.medications?.length > 0 && (
              <div className="p-3 bg-green-50 rounded-lg">
                <p className="text-xs text-green-600 mb-2">Medications</p>
                <div className="flex flex-wrap gap-2">
                  {parsed.medications.map((m, i) => (
                    <span key={i} className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Lab Values */}
            {parsed.lab_values?.length > 0 && (
              <div className="p-3 bg-purple-50 rounded-lg">
                <p className="text-xs text-purple-600 mb-2">Lab Values</p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {parsed.lab_values.map((lab, i) => (
                    <div key={i} className="bg-white p-2 rounded border border-purple-100">
                      <p className="text-xs text-gray-500">{lab.name}</p>
                      <p className="font-medium">{lab.value} {lab.unit}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Lifestyle */}
            {parsed.lifestyle && (
              <div className="p-3 bg-amber-50 rounded-lg">
                <p className="text-xs text-amber-600 mb-2">Lifestyle Factors</p>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500">Smoking: </span>
                    <span className="font-medium">{parsed.lifestyle.smoking || 'Unknown'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Alcohol: </span>
                    <span className="font-medium">{parsed.lifestyle.alcohol || 'Unknown'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Exercise: </span>
                    <span className="font-medium">{parsed.lifestyle.exercise || 'Unknown'}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Risk Signals (for full brief) */}
            {parsed.risk_signals?.length > 0 && (
              <div className="p-3 bg-red-50 rounded-lg">
                <p className="text-xs text-red-600 mb-2 flex items-center">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Risk Signals
                </p>
                <ul className="space-y-1">
                  {parsed.risk_signals.map((risk, i) => (
                    <li key={i} className="text-sm text-red-800 flex items-start">
                      <span className="w-1.5 h-1.5 bg-red-500 rounded-full mt-2 mr-2" />
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Information Gaps (for full brief) */}
            {parsed.information_gaps?.length > 0 && (
              <div className="p-3 bg-orange-50 rounded-lg">
                <p className="text-xs text-orange-600 mb-2 flex items-center">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  Information Gaps
                </p>
                <ul className="space-y-1">
                  {parsed.information_gaps.map((gap, i) => (
                    <li key={i} className="text-sm text-orange-800 flex items-start">
                      <span className="w-1.5 h-1.5 bg-orange-500 rounded-full mt-2 mr-2" />
                      {gap}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Evidence */}
            {parsed.evidence?.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-gray-500 mb-2">Evidence Citations</p>
                <div className="space-y-2">
                  {parsed.evidence.map((ev, idx) => (
                    <div key={idx} className="flex items-start p-2 bg-gray-50 rounded text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="font-medium text-gray-700">{ev.field}: </span>
                        <span className="text-gray-600">"{ev.quote}"</span>
                        {ev.confidence && (
                          <span className="ml-2 text-xs text-gray-400">
                            ({(ev.confidence * 100).toFixed(0)}% confident)
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Timeline (for full brief) */}
            {parsed.timeline_summary && (
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 mb-1">Timeline Summary</p>
                <p className="text-sm text-gray-700">{parsed.timeline_summary}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function CaseBrief() {
  const [query, setQuery] = useState('')
  const [patientId, setPatientId] = useState('')
  const [mode, setMode] = useState('quick') // 'quick' or 'full'
  
  // Fetch CrewAI status
  const statusQuery = useQuery({
    queryKey: ['crewStatus'],
    queryFn: () => getCrewStatus(),
    refetchInterval: 30000,
  })
  
  // Fetch agents list
  const agentsQuery = useQuery({
    queryKey: ['crewAgents'],
    queryFn: () => getCrewAgents(),
  })
  
  // Quick extraction mutation
  const quickMutation = useMutation({
    mutationFn: () => crewQuickExtract(query, patientId || null),
  })
  
  // Full case brief mutation
  const fullMutation = useMutation({
    mutationFn: () => crewCaseBrief(query, patientId || null),
  })
  
  const activeMutation = mode === 'quick' ? quickMutation : fullMutation
  const isLoading = activeMutation.isPending
  
  const handleSubmit = (e) => {
    e.preventDefault()
    if (query.trim()) {
      activeMutation.mutate()
    }
  }
  
  const status = statusQuery.data?.data
  const agents = agentsQuery.data?.data?.agents || []
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center">
            <Users className="w-6 h-6 text-purple-500 mr-2" />
            AI Case Brief
          </h2>
          <p className="text-gray-500 mt-1">
            Multi-agent clinical documentation powered by CrewAI
          </p>
        </div>
        
        {/* Status Badge */}
        {status && (
          <div className={clsx(
            'px-3 py-1 rounded-full text-sm flex items-center',
            status.status === 'ready' 
              ? 'bg-green-100 text-green-800' 
              : 'bg-amber-100 text-amber-800'
          )}>
            <Activity className="w-4 h-4 mr-1" />
            {status.agents_initialized || 0} agents ready
          </div>
        )}
      </div>
      
      {/* Agents Overview */}
      {agents.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-700">Available Agents</h3>
            <span className="text-xs text-gray-500">
              {mode === 'quick' ? '2 agents' : '5 agents'} will be used
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
            {agents.map((agent, idx) => (
              <AgentCard 
                key={idx} 
                agent={agent} 
                isActive={isLoading && (
                  mode === 'full' || 
                  (mode === 'quick' && idx < 2)
                )}
              />
            ))}
          </div>
        </div>
      )}
      
      {/* Mode Selection & Search */}
      <div className="card">
        {/* Mode Toggle */}
        <div className="flex space-x-2 mb-4">
          <button
            onClick={() => setMode('quick')}
            className={clsx(
              'flex-1 py-3 px-4 rounded-lg border-2 transition-all flex items-center justify-center',
              mode === 'quick'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
            )}
          >
            <Zap className="w-5 h-5 mr-2" />
            <div className="text-left">
              <p className="font-medium">Quick Extract</p>
              <p className="text-xs opacity-75">2 agents • ~15 seconds</p>
            </div>
          </button>
          <button
            onClick={() => setMode('full')}
            className={clsx(
              'flex-1 py-3 px-4 rounded-lg border-2 transition-all flex items-center justify-center',
              mode === 'full'
                ? 'border-purple-500 bg-purple-50 text-purple-700'
                : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
            )}
          >
            <Brain className="w-5 h-5 mr-2" />
            <div className="text-left">
              <p className="font-medium">Full Case Brief</p>
              <p className="text-xs opacity-75">5 agents • ~60 seconds</p>
            </div>
          </button>
        </div>
        
        {/* Search Form */}
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Clinical Query
              </label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., Prepare case brief for diabetes patient with recent HbA1c changes..."
                className="input-field min-h-[100px]"
                rows={3}
                disabled={isLoading}
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
                disabled={isLoading}
              />
            </div>
            
            <button
              type="submit"
              disabled={!query.trim() || isLoading}
              className={clsx(
                'w-full flex items-center justify-center py-3 px-4 rounded-lg font-medium transition-all',
                mode === 'quick' 
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-purple-600 hover:bg-purple-700 text-white',
                (isLoading || !query.trim()) && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  <span>AI Agents Working...</span>
                  <Clock className="w-4 h-4 ml-2 opacity-75" />
                </>
              ) : (
                <>
                  {mode === 'quick' ? (
                    <Zap className="w-5 h-5 mr-2" />
                  ) : (
                    <Brain className="w-5 h-5 mr-2" />
                  )}
                  {mode === 'quick' ? 'Quick Extract' : 'Generate Case Brief'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
      
      {/* Loading State */}
      {isLoading && (
        <div className="card bg-gradient-to-r from-blue-50 to-purple-50">
          <div className="flex items-center justify-center py-8">
            <div className="text-center">
              <div className="relative">
                <Brain className="w-12 h-12 text-purple-500 mx-auto mb-4" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-500 rounded-full animate-spin" />
                </div>
              </div>
              <p className="font-medium text-gray-800">
                {mode === 'quick' ? 'Quick extraction in progress...' : 'Full case brief generation in progress...'}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {mode === 'quick' 
                  ? 'Retriever and Extractor agents are working'
                  : 'All 5 agents are collaborating on your case brief'
                }
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Error */}
      {activeMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="w-5 h-5 text-red-500 mr-3 mt-0.5" />
          <div>
            <p className="font-medium text-red-800">Analysis failed</p>
            <p className="text-sm text-red-600">
              {activeMutation.error?.message || 'Unknown error occurred'}
            </p>
          </div>
        </div>
      )}
      
      {/* Results */}
      {activeMutation.isSuccess && (
        <CaseBriefResults 
          data={activeMutation.data?.data}
          isQuickMode={mode === 'quick'}
        />
      )}
      
      {/* Example Queries */}
      {!activeMutation.data && !isLoading && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Example Queries</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              'Diabetes patient medications and HbA1c trends',
              'Cardiac patient with recent hospitalization',
              'COPD patient follow-up preparation',
              'Elderly patient medication reconciliation',
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
      
      {/* Info Footer */}
      <div className="text-center text-xs text-gray-400 py-4">
        <Shield className="w-4 h-4 inline mr-1" />
        All patient data is de-identified. AI agents work only with masked information.
      </div>
    </div>
  )
}
