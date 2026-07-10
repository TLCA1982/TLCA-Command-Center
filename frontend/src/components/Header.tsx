type HeaderProps = {
  eyebrow: string
  title: string
}

const Header = ({ eyebrow, title }: HeaderProps) => {
  return (
    <header className="topbar">
      <div>
        <p className="topbar__eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
    </header>
  )
}

export default Header
