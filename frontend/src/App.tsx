import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Dossiers from './pages/Dossiers'
import Companies from './pages/Companies'
import Header from './components/Header'
import './styles.css'

const App = () => {
  const [page, setPage] = useState<'actions' | 'dossiers' | 'companies'>('actions')
  return (
    <div>
      <Header eyebrow="CRM overzicht" title={page === 'actions' ? 'TLCA Command Center' : page === 'dossiers' ? 'Dossiers' : 'Bedrijven'} active={page} onNavigate={setPage} />
      {page === 'actions' ? <Dashboard /> : page === 'dossiers' ? <Dossiers /> : <Companies />}
    </div>
  )
}

export default App
