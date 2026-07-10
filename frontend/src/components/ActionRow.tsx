import type { Action } from '../types/Action'

type ActionRowProps = {
  action: Action
}

const createClassName = (value: string) => value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')

const ActionRow = ({ action }: ActionRowProps) => {
  return (
    <tr>
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
      <td>{action.dueDate}</td>
      <td>
        <span className={`status-pill status-pill--${createClassName(action.status)}`}>{action.status}</span>
      </td>
    </tr>
  )
}

export default ActionRow
