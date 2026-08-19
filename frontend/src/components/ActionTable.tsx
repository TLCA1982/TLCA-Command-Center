import ActionRow from './ActionRow'
import type { Action } from '../types/Action'

type ActionTableProps = {
  actions: Action[]
  activeFilter: string
  loading?: boolean
  error?: string | null
  showCompleted?: boolean
  onToggleCompleted?: (value: boolean) => void
  onCreate?: () => void
  onEdit?: (action: Action) => void
  noResultsMessage?: string
  searchValue?: string
  onSearchChange?: (s: string) => void
}
const ActionTable = ({ actions, activeFilter, loading = false, error = null, showCompleted = false, onToggleCompleted, onCreate, onEdit, noResultsMessage, searchValue, onSearchChange }: ActionTableProps) => {
  // keep activeFilter referenced to avoid unused variable TypeScript error
  void activeFilter

  const statusMessage = loading
    ? 'Microsoft acties worden geladen...'
    : error
      ? error
      : actions.length === 0
        ? (noResultsMessage ?? 'Geen acties gevonden voor deze selectie.')
        : null

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <h2>Acties</h2>
          {typeof onSearchChange === 'function' && (
            <div style={{ marginTop: 8 }}>
              <input
                placeholder="Zoeken op klant..."
                value={searchValue ?? ''}
                onChange={(e) => onSearchChange(e.target.value)}
                style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid #e2e8f0', width: 260 }}
              />
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button type="button" className="action-btn action-btn--primary" onClick={() => onCreate?.()}>
            + Nieuwe actie
          </button>
          <div role="group" aria-label="Acties filter">
            <button
              type="button"
              className={`action-btn action-btn--secondary ${!showCompleted ? 'action-btn--active' : ''}`}
              onClick={() => onToggleCompleted?.(false)}
              aria-pressed={!showCompleted}
              style={{ marginRight: 6 }}
            >
              Alle acties
            </button>
            <button type="button" className={`action-btn action-btn--secondary ${showCompleted ? 'action-btn--active' : ''}`} onClick={() => onToggleCompleted?.(true)} aria-pressed={showCompleted}>
              Afgewerkt
            </button>
          </div>
        </div>
      </div>

      {statusMessage ? (
        <div className="table-wrapper">
          <p className="table-card__subtitle">{statusMessage}</p>
        </div>
      ) : (
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
                <ActionRow key={`${action.id ?? action.title}-${action.customer}`} action={action} onClick={onEdit} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default ActionTable
