import type { Action } from '../types/Action'
import { isoToBelgian } from '../utils/date'

type ActionRowProps = {
  action: Action
  onClick?: (action: Action) => void
  selected?: boolean
  selectable?: boolean
  onToggleSelected?: (action: Action) => void
}

const createClassName = (value: string) => value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')

const ActionRow = ({ action, onClick, selected = false, selectable = false, onToggleSelected }: ActionRowProps) => {
  // allow clicking both Command Center and Microsoft/Outlook sourced actions for (limited) edits
  const clickable = action.source === 'Command Center' || action.source === 'Microsoft To Do' || action.source === 'Outlook gemarkeerde mail' || action.source === 'Dossier'
  return (
    <tr onClick={() => clickable && onClick?.(action)} style={clickable ? { cursor: 'pointer' } : undefined}>
      <td>
        <input
          type="checkbox"
          checked={selected}
          disabled={!selectable}
          aria-label={`Selecteer ${action.title}`}
          onChange={() => onToggleSelected?.(action)}
          onClick={(event) => event.stopPropagation()}
        />
      </td>
      <td>
        <span className={`priority priority--${createClassName(action.priority)}`}>{action.priority}</span>
      </td>
      <td>{action.title}</td>
      <td>
        <div className="customer-cell">
          <span className="customer-cell__name">{action.customer}</span>
          <span className="customer-cell__contact">{action.contact}</span>
        </div>
      </td>
      <td>
        {action.source === 'Outlook gemarkeerde mail' && action.senderName ? (
          <div className="customer-cell">
            <span className="customer-cell__name">{action.source}</span>
            <span className="customer-cell__contact">{action.senderName}</span>
          </div>
        ) : (
          action.source
        )}
      </td>
      <td>{isoToBelgian(action.dueDate)}</td>
      <td>
        <span className={`status-pill status-pill--${createClassName(action.status)}`}>{action.status}</span>
      </td>
    </tr>
  )
}

export default ActionRow
