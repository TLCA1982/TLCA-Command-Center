import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Dossiers from './pages/Dossiers'
import Header from './components/Header'
import './styles.css'

const App = () => {
  const [page, setPage] = useState<'actions' | 'dossiers'>('actions')
  return (
    <div>
      <Header eyebrow="CRM overzicht" title={page === 'actions' ? 'TLCA Command Center' : 'Dossiers'} active={page} onNavigate={setPage} />
      {page === 'actions' ? <Dashboard /> : <Dossiers />}
    </div>
  )
}

export default App
