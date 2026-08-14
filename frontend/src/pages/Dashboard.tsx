import { useMemo, useState } from 'react'
import Header from '../components/Header'
import DashboardCards from '../components/DashboardCards'
import ActionTable from '../components/ActionTable'
import { sampleData } from '../data/sampleData'

const matchesFilter = (action: (typeof sampleData.actions)[number], filter: string) => {
  switch (filter) {
    case 'today':
      return action.group === 'today'
    case 'waiting':
      return action.status === 'Wacht op klant' || action.status === 'Wacht op leverancier'
    case 'offers':
      return action.group === 'offers'
    case 'urgent':
      return action.group === 'urgent'
    default:
      return true
  }
}

const Dashboard = () => {
  const [activeFilter, setActiveFilter] = useState<string>('all')

  const summaryCards = useMemo(
    () =>
      sampleData.summaryCards.map((card) => ({
        ...card,
        value: String(sampleData.actions.filter((action) => matchesFilter(action, card.filter)).length),
      })),
    [],
  )

  const visibleActions = useMemo(() => {
    if (activeFilter === 'all') return sampleData.actions
    return sampleData.actions.filter((action) => matchesFilter(action, activeFilter))
  }, [activeFilter])

  return (
    <div className="app-shell">
      <Header eyebrow="CRM overzicht" title="TLCA Command Center" />

      <main className="content">
        <DashboardCards
          cards={summaryCards}
          activeFilter={activeFilter}
          onSelectFilter={(filter) => setActiveFilter((current) => (current === filter ? 'all' : filter))}
        />
        <ActionTable actions={visibleActions} activeFilter={activeFilter} />
      </main>
    </div>
  )
}

export default Dashboard
