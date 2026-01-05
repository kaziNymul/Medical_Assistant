import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  Shield, 
  Key, 
  Server, 
  CheckCircle, 
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Database,
  Loader2
} from 'lucide-react'
import { getHealth, getDatabricksStatus, syncToDatabricks, getCrewStatus } from '../utils/api'
import clsx from 'clsx'

function SettingSection({ title, description, children }) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 mb-4">{description}</p>
      {children}
    </div>
  )
}

function ConfigItem({ label, value, status, secret = false }) {
  const displayValue = secret && value ? '••••••••' : (value || 'Not configured')
  
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <div className="flex items-center">
        <span className={clsx(
          'text-sm font-mono',
          value ? 'text-gray-900' : 'text-gray-400'
        )}>
          {displayValue}
        </span>
        {status !== undefined && (
          status ? (
            <CheckCircle className="w-4 h-4 text-green-500 ml-2" />
          ) : (
            <AlertCircle className="w-4 h-4 text-gray-400 ml-2" />
          )
        )}
      </div>
    </div>
  )
}

export default function Settings() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => getHealth().then(r => r.data),
  })
  
  const { data: databricksStatus, isLoading: dbLoading, refetch: refetchDb } = useQuery({
    queryKey: ['databricksStatus'],
    queryFn: () => getDatabricksStatus().then(r => r.data),
    retry: false,
  })
  
  const { data: crewStatus } = useQuery({
    queryKey: ['crewStatus'],
    queryFn: () => getCrewStatus().then(r => r.data),
  })
  
  const syncMutation = useMutation({
    mutationFn: () => syncToDatabricks(),
  })
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Settings</h2>
        <p className="text-gray-500 mt-1">
          System configuration and secrets management
        </p>
      </div>
      
      {/* Vault Configuration */}
      <SettingSection
        title="HashiCorp Vault"
        description="Secure secrets management for credentials and API keys"
      >
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div className="flex items-start">
            <Key className="w-5 h-5 text-blue-500 mr-3 mt-0.5" />
            <div>
              <p className="text-sm text-blue-800 font-medium">
                Secrets are managed via HashiCorp Vault
              </p>
              <p className="text-sm text-blue-600 mt-1">
                AWS credentials and other secrets are fetched from Vault at runtime.
                Environment variables are used as fallback.
              </p>
            </div>
          </div>
        </div>
        
        <div className="space-y-1">
          <ConfigItem label="Vault Address" value="http://127.0.0.1:8200" />
          <ConfigItem label="Vault Path" value="secret/data/medical-assistant" />
          <ConfigItem label="Connection Status" value="Checking..." status={false} />
        </div>
        
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Setup Instructions</h4>
          <ol className="text-sm text-gray-600 space-y-2 list-decimal list-inside">
            <li>Install Vault: <code className="bg-gray-100 px-1 rounded">brew install vault</code></li>
            <li>Start dev server: <code className="bg-gray-100 px-1 rounded">vault server -dev</code></li>
            <li>Set environment: <code className="bg-gray-100 px-1 rounded">export VAULT_ADDR=http://127.0.0.1:8200</code></li>
            <li>Store secrets: <code className="bg-gray-100 px-1 rounded">vault kv put secret/medical-assistant AWS_ACCESS_KEY_ID=xxx</code></li>
          </ol>
        </div>
      </SettingSection>
      
      {/* AWS Bedrock */}
      <SettingSection
        title="AWS Bedrock (Phase 2)"
        description="Cloud-based LLM for production inference"
      >
        <div className="space-y-1">
          <ConfigItem label="LLM Provider" value={health?.llm_provider || 'local'} />
          <ConfigItem label="AWS Region" value="us-east-1" />
          <ConfigItem label="Bedrock Model" value="anthropic.claude-3-5-sonnet" />
          <ConfigItem label="AWS Access Key" value={null} secret status={false} />
          <ConfigItem label="AWS Secret Key" value={null} secret status={false} />
        </div>
        
        <a
          href="https://aws.amazon.com/bedrock/"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center text-sm text-primary-600 hover:text-primary-700"
        >
          Learn about AWS Bedrock
          <ExternalLink className="w-4 h-4 ml-1" />
        </a>
      </SettingSection>
      
      {/* Databricks */}
      <SettingSection
        title="Databricks Integration"
        description="Enterprise data lakehouse for analytics and compliance"
      >
        {/* Connection Status */}
        <div className={clsx(
          'mb-4 p-4 rounded-lg border flex items-center justify-between',
          databricksStatus?.connected 
            ? 'bg-green-50 border-green-200' 
            : 'bg-amber-50 border-amber-200'
        )}>
          <div className="flex items-center">
            <Database className={clsx(
              'w-5 h-5 mr-3',
              databricksStatus?.connected ? 'text-green-500' : 'text-amber-500'
            )} />
            <div>
              <p className={clsx(
                'font-medium',
                databricksStatus?.connected ? 'text-green-800' : 'text-amber-800'
              )}>
                {dbLoading 
                  ? 'Checking connection...' 
                  : databricksStatus?.connected 
                    ? 'Connected to Databricks' 
                    : 'Not connected'
                }
              </p>
              {databricksStatus?.user && (
                <p className="text-sm text-green-600">
                  Logged in as: {databricksStatus.user}
                </p>
              )}
            </div>
          </div>
          <button 
            onClick={() => refetchDb()}
            className="p-2 hover:bg-white rounded-lg transition-colors"
          >
            <RefreshCw className={clsx('w-4 h-4', dbLoading && 'animate-spin')} />
          </button>
        </div>
        
        <div className="space-y-1">
          <ConfigItem 
            label="Databricks Host" 
            value={databricksStatus?.host || 'Not configured'} 
            status={!!databricksStatus?.host} 
          />
          <ConfigItem label="Databricks Token" value={databricksStatus?.connected ? 'Configured' : null} secret status={databricksStatus?.connected} />
          <ConfigItem label="Catalog" value={databricksStatus?.catalog || 'healthcare_ai'} />
          <ConfigItem label="Schema" value={databricksStatus?.schema || 'clinical_docs'} />
        </div>
        
        {/* Sync Button */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-700">Sync to Databricks</p>
              <p className="text-sm text-gray-500">Push PII data for secure storage and analytics</p>
            </div>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={!databricksStatus?.connected || syncMutation.isPending}
              className={clsx(
                'flex items-center px-4 py-2 rounded-lg font-medium transition-colors',
                databricksStatus?.connected
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              )}
            >
              {syncMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
            </button>
          </div>
          
          {syncMutation.isSuccess && (
            <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-700">
                <CheckCircle className="w-4 h-4 inline mr-1" />
                Sync completed successfully
              </p>
            </div>
          )}
          
          {syncMutation.isError && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">
                <AlertCircle className="w-4 h-4 inline mr-1" />
                Sync failed: {syncMutation.error?.message}
              </p>
            </div>
          )}
        </div>
      </SettingSection>
      
      {/* Security Settings */}
      <SettingSection
        title="Security"
        description="Privacy and data protection settings"
      >
        <div className="space-y-1">
          <ConfigItem label="PII Masking" value="Enabled" status={true} />
          <ConfigItem label="Masking Mode" value="HIPAA Safe Harbor" />
          <ConfigItem label="Min Confidence Threshold" value="0.7" />
          <ConfigItem label="Audit Logging" value="Enabled" status={true} />
        </div>
        
        <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-start">
            <Shield className="w-5 h-5 text-green-500 mr-3 mt-0.5" />
            <div>
              <p className="text-sm text-green-800 font-medium">
                HIPAA-style de-identification active
              </p>
              <p className="text-sm text-green-600 mt-1">
                All patient data is automatically masked before storage and AI processing.
              </p>
            </div>
          </div>
        </div>
      </SettingSection>
      
      {/* System Info */}
      <SettingSection
        title="System Information"
        description="Current system configuration"
      >
        <div className="space-y-1">
          <ConfigItem label="Version" value={health?.version || '0.1.0'} />
          <ConfigItem label="Environment" value={health?.environment || 'development'} />
          <ConfigItem label="API Status" value={health?.status} status={health?.status === 'healthy'} />
          <ConfigItem label="LLM Provider" value={health?.llm_provider === 'bedrock' ? 'AWS Bedrock' : 'Local'} status={health?.llm_provider === 'bedrock'} />
          <ConfigItem label="LLM Model" value="Claude 3 Haiku" />
          <ConfigItem label="Embedding Model" value="Titan Text Embed v2" />
          <ConfigItem label="Vector Store" value="FAISS (55,500 chunks)" status={true} />
          <ConfigItem label="CrewAI Agents" value={`${crewStatus?.agents_initialized || 0} agents ready`} status={crewStatus?.status === 'ready'} />
        </div>
      </SettingSection>
    </div>
  )
}
