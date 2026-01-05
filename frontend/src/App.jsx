import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Query from './pages/Query'
import CaseBrief from './pages/CaseBrief'
import Documents from './pages/Documents'
import DataPipeline from './pages/DataPipeline'
import Settings from './pages/Settings'
import IntelligentExtraction from './pages/IntelligentExtraction'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="query" element={<Query />} />
        <Route path="case-brief" element={<CaseBrief />} />
        <Route path="extract" element={<IntelligentExtraction />} />
        <Route path="documents" element={<Documents />} />
        <Route path="data" element={<DataPipeline />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
