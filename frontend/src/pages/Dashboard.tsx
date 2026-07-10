import { useMemo, useState } from 'react'
import Header from '../components/Header'
import DashboardCards from '../components/DashboardCards'
import ActionTable from '../components/ActionTable'
import { sampleData } from '../data/sampleData'

const Dashboard = () => {
  const [activeFilter, setActiveFilter] = useState<string>('all')

  const visibleActions = useMemo(() => {
    if (activeFilter === 'all') return sampleData.actions
    return sampleData.actions.filter((action) => action.group === activeFilter)
  }, [activeFilter])

  return (
    <div className="app-shell">
      <Header eyebrow="CRM overzicht" title="TLCA Command Center" />

      <main className="content">
        <DashboardCards cards={sampleData.summaryCards} activeFilter={activeFilter} onSelectFilter={setActiveFilter} />
        <ActionTable actions={visibleActions} activeFilter={activeFilter} />
      </main>
    </div>
  )
}

export default Dashboard
