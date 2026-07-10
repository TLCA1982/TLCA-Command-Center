import ActionRow from './ActionRow'
import type { Action } from '../types/Action'

type ActionTableProps = {
  actions: Action[]
  activeFilter: string
}

const ActionTable = ({ actions, activeFilter }: ActionTableProps) => {
  const subtitle = activeFilter === 'all' ? 'Alle acties' : activeFilter === 'today' ? 'Vandaag' : activeFilter === 'waiting' ? 'In behandeling' : activeFilter === 'offers' ? 'Offertes' : 'Dossiers'

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <h2>Acties</h2>
          <p className="table-card__subtitle">{subtitle}</p>
        </div>
        <span>Vandaag</span>
      </div>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Prioriteit</th>
              <th>Actie</th>
              <th>Klant</th>
              <th>Bron</th>
              <th>Vervaldatum</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => (
              <ActionRow key={`${action.title}-${action.customer}`} action={action} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ActionTable
