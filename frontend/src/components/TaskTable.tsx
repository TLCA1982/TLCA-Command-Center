type Task = {
  priority: string
  title: string
  customer: string
  contact: string
  source: string
  dueDate: string
  status: string
  group: string
}

type TaskTableProps = {
  tasks: Task[]
  activeFilter: string
}

const createClassName = (value: string) => value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')

const TaskTable = ({ tasks, activeFilter }: TaskTableProps) => {
  // keep activeFilter referenced to avoid unused variable TypeScript error after subtitle removal
  void activeFilter

  return (
    <div className="table-card">
      <div className="table-card__header">
        <div>
          <h2>Acties</h2>
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
            {tasks.map((task) => (
              <tr key={`${task.title}-${task.customer}`}>
                <td>
                  <span className={`priority priority--${createClassName(task.priority)}`}>{task.priority}</span>
                </td>
                <td>{task.title}</td>
                <td>
                  <div className="customer-cell">
                    <span className="customer-cell__name">{task.customer}</span>
                    <span className="customer-cell__contact">{task.contact}</span>
                  </div>
                </td>
                <td>{task.source}</td>
                <td>{task.dueDate}</td>
                <td>
                  <span className={`status-pill status-pill--${createClassName(task.status)}`}>{task.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default TaskTable
