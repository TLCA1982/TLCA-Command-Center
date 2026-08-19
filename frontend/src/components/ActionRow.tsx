import type { Action } from '../types/Action'
import { isoToBelgian } from '../utils/date'

type ActionRowProps = {
  action: Action
  onClick?: (action: Action) => void
}

const createClassName = (value: string) => value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')

const ActionRow = ({ action, onClick }: ActionRowProps) => {
  // allow clicking both Command Center and Microsoft/Outlook sourced actions for (limited) edits
  const clickable = action.source === 'Command Center' || action.source === 'Microsoft To Do' || action.source === 'Outlook gemarkeerde mail' || action.source === 'Dossier'
  return (
    <tr onClick={() => clickable && onClick?.(action)} style={clickable ? { cursor: 'pointer' } : undefined}>
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
      <td>{action.source}</td>
      <td>{isoToBelgian(action.dueDate)}</td>
      <td>
        <span className={`status-pill status-pill--${createClassName(action.status)}`}>{action.status}</span>
      </td>
    </tr>
  )
}

export default ActionRow
