type StatCardProps = {
  title: string
  value: string
  icon: string
  accent: string
  isActive?: boolean
  onClick?: () => void
}

const StatCard = ({ title, value, icon, accent, isActive = false, onClick }: StatCardProps) => {
  return (
    <button
      type="button"
      className={`stat-card${isActive ? ' stat-card--active' : ''}`}
      onClick={onClick}
      aria-pressed={isActive}
      style={{ ['--accent' as string]: accent }}
    >
      <span className="stat-card__icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        <p className="stat-card__title">{title}</p>
        <p className="stat-card__value">{value}</p>
      </div>
    </button>
  )
}

export default StatCard
