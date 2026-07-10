import DashboardCard from './DashboardCard'

type SummaryCard = {
  title: string
  value: string
  icon: string
  accent: string
  filter: string
}

type DashboardCardsProps = {
  cards: SummaryCard[]
  activeFilter: string
  onSelectFilter: (filter: string) => void
}

const DashboardCards = ({ cards, activeFilter, onSelectFilter }: DashboardCardsProps) => {
  return (
    <section className="card-grid" aria-label="Dashboard overview">
      {cards.map((card) => (
        <DashboardCard
          key={card.title}
          title={card.title}
          value={card.value}
          icon={card.icon}
          accent={card.accent}
          isActive={activeFilter === card.filter}
          onClick={() => onSelectFilter(card.filter)}
        />
      ))}
    </section>
  )
}

export default DashboardCards
