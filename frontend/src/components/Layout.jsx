import { Outlet, NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Search, 
  FileText, 
  Database, 
  Settings,
  Activity,
  Shield,
  Users,
  Brain
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../utils/api'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Query', href: '/query', icon: Search },
  { name: 'AI Case Brief', href: '/case-brief', icon: Users, badge: 'CrewAI' },
  { name: 'Smart Extract', href: '/extract', icon: Brain, badge: 'Local LLM' },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Data Pipeline', href: '/data', icon: Database },
  { name: 'Settings', href: '/settings', icon: Settings },
]

function Sidebar() {
  return (
    <div className="flex flex-col w-64 bg-gray-900 min-h-screen">
      {/* Logo */}
      <div className="flex items-center h-16 px-4 bg-gray-800">
        <Shield className="w-8 h-8 text-healthcare-500" />
        <span className="ml-2 text-white font-semibold text-lg">Medical AI</span>
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) => clsx(
              'flex items-center px-4 py-2.5 text-sm font-medium rounded-lg transition-colors',
              isActive
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            )}
          >
            <item.icon className="w-5 h-5 mr-3" />
            <span className="flex-1">{item.name}</span>
            {item.badge && (
              <span className="ml-2 px-1.5 py-0.5 text-xs bg-purple-500 text-white rounded">
                {item.badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      
      {/* Footer */}
      <div className="px-4 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-500">
          AI Clinical Documentation
        </p>
        <p className="text-xs text-gray-600">
          v1.0.0 • Phase 1
        </p>
      </div>
    </div>
  )
}

function Header() {
  const { data: health, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => getHealth().then(r => r.data),
    refetchInterval: 30000,
  })
  
  return (
    <header className="bg-white border-b border-gray-200 h-16 flex items-center px-6 justify-between">
      <h1 className="text-xl font-semibold text-gray-800">
        AI Clinical Documentation Assistant
      </h1>
      
      <div className="flex items-center space-x-4">
        {/* Status Indicator */}
        <div className="flex items-center">
          <Activity className={clsx(
            'w-4 h-4 mr-2',
            health?.status === 'healthy' ? 'text-green-500' : 'text-gray-400'
          )} />
          <span className={clsx(
            'text-sm font-medium',
            health?.status === 'healthy' ? 'text-green-600' : 'text-gray-500'
          )}>
            {isLoading ? 'Checking...' : health?.status === 'healthy' ? 'System Healthy' : 'Offline'}
          </span>
        </div>
        
        {/* Environment Badge */}
        <span className="badge-info">
          {health?.environment || 'development'}
        </span>
      </div>
    </header>
  )
}

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
