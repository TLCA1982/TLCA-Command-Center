import ActionRow from './ActionRow'
import type { Action } from '../types/Action'

type SortKey = 'priority' | 'title' | 'customer' | 'source' | 'dueDate' | 'status'
type SortDirection = 'asc' | 'desc'

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
  selectedActionIds?: Set<string>
  onToggleSelected?: (action: Action) => void
  onToggleSelectAll?: (checked: boolean) => void
  onDeleteSelected?: () => void
  sortKey?: SortKey
  sortDirection?: SortDirection
  onSortChange?: (sortKey: SortKey) => void
}
const ActionTable = ({ actions, activeFilter, loading = false, error = null, showCompleted = false, onToggleCompleted, onCreate, onEdit, noResultsMessage, searchValue, onSearchChange, selectedActionIds = new Set<string>(), onToggleSelected, onToggleSelectAll, onDeleteSelected, sortKey, sortDirection, onSortChange }: ActionTableProps) => {
  // keep activeFilter referenced to avoid unused variable TypeScript error
  void activeFilter

  const statusMessage = loading
    ? 'Microsoft acties worden geladen...'
    : error
      ? error
      : actions.length === 0
        ? (noResultsMessage ?? 'Geen acties gevonden voor deze selectie.')
        : null
  const selectableActions = actions.filter((action) => !!action.id && (action.source === 'Command Center' || action.source === 'Microsoft To Do' || action.source === 'Outlook gemarkeerde mail'))
  const allVisibleSelected = selectableActions.length > 0 && selectableActions.every((action) => selectedActionIds.has(action.id as string))
  const selectedCount = selectedActionIds.size

  const sortableHeader = (key: SortKey, label: string) => (
    <button
      type="button"
      onClick={() => onSortChange?.(key)}
      style={{ border: 0, background: 'none', padding: 0, font: 'inherit', color: 'inherit', cursor: 'pointer' }}
      aria-label={`Sorteer op ${label}`}
    >
      {label}
      {sortKey === key && <span aria-hidden="true" style={{ marginLeft: 4, opacity: 0.65 }}>{sortDirection === 'asc' ? '↑' : '↓'}</span>}
    </button>
  )

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
          {selectedCount > 0 && (
            <button type="button" className="action-btn action-btn--secondary" onClick={() => onDeleteSelected?.()}>
              Verwijder geselecteerde ({selectedCount})
            </button>
          )}
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
                <th>
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    disabled={selectableActions.length === 0}
                    aria-label="Selecteer zichtbare acties"
                    onChange={(event) => onToggleSelectAll?.(event.target.checked)}
                  />
                </th>
                <th>{sortableHeader('priority', 'Prioriteit')}</th>
                <th>{sortableHeader('title', 'Actie')}</th>
                <th>{sortableHeader('customer', 'Klant')}</th>
                <th>{sortableHeader('source', 'Bron')}</th>
                <th>{sortableHeader('dueDate', 'Vervaldatum')}</th>
                <th>{sortableHeader('status', 'Status')}</th>
              </tr>
            </thead>
            <tbody>
              {actions.map((action) => (
                <ActionRow
                  key={`${action.id ?? action.title}-${action.customer}`}
                  action={action}
                  onClick={onEdit}
                  selected={!!action.id && selectedActionIds.has(action.id)}
                  selectable={!!action.id && (action.source === 'Command Center' || action.source === 'Microsoft To Do' || action.source === 'Outlook gemarkeerde mail')}
                  onToggleSelected={onToggleSelected}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default ActionTable
