type HeaderProps = {
  eyebrow: string
  title: string
  active?: 'actions' | 'dossiers' | 'companies'
  onNavigate?: (page: 'actions' | 'dossiers' | 'companies') => void
}

const Header = ({ eyebrow, title, active = 'actions', onNavigate }: HeaderProps) => {
  return (
    <header className="topbar">
      <div>
        <p className="topbar__eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>

      <nav className="topbar__nav" aria-label="Primary">
        <button
          type="button"
          className={`topbar__navitem ${active === 'actions' ? 'topbar__navitem--active' : ''}`}
          onClick={() => onNavigate && onNavigate('actions')}
        >
          Acties
        </button>
        <button
          type="button"
          className={`topbar__navitem ${active === 'dossiers' ? 'topbar__navitem--active' : ''}`}
          onClick={() => onNavigate && onNavigate('dossiers')}
        >
          Dossiers
        </button>
        <button
          type="button"
          className={`topbar__navitem ${active === 'companies' ? 'topbar__navitem--active' : ''}`}
          onClick={() => onNavigate && onNavigate('companies')}
        >
          Bedrijven
        </button>
      </nav>
    </header>
  )
}

export default Header
