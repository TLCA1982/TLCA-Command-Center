import { useEffect, useMemo, useState } from 'react'
// Header is rendered at the app root now
import DashboardCards from '../components/DashboardCards'
import ActionTable from '../components/ActionTable'
import ManualActionModal from '../components/ManualActionModal'
import DossierDetail from '../components/DossierDetail'
import type { Action } from '../types/Action'

type MicrosoftActionResponse = {
  id?: string
  title?: string
  source?: string
  status?: string
  priority?: string
  dueDate?: string
  createdDate?: string
  lastModifiedDate?: string
  customer?: string
  contact?: string
  notes?: string
  webLink?: string
  microsoftList?: string
}

type SummaryCard = {
  title: string
  value: string
  icon: string
  accent: string
  filter: string
}

const summaryCardDefinitions: SummaryCard[] = [
  { title: 'Vandaag', value: '0', icon: '📅', accent: '#2563eb', filter: 'today' },
  { title: 'Wachtend', value: '0', icon: '⏳', accent: '#f59e0b', filter: 'waiting' },
  { title: 'Open offertes', value: '0', icon: '📄', accent: '#10b981', filter: 'offers' },
  { title: 'Opvolgen', value: '0', icon: '⚠️', accent: '#ef4444', filter: 'urgent' },
]

import { parseIsoToDate } from '../utils/date'

const hasDueDate = (dateValue: string | undefined) => {
  if (!dateValue) return false
  const parsed = parseIsoToDate(dateValue)
  return parsed !== null && !Number.isNaN(parsed.getTime())
}

const normalizeStatus = (status: string | undefined) => {
  switch (status) {
    case 'Open':
    case 'notStarted':
    case 'inProgress':
      return 'Open'
    case 'Afgewerkt':
    case 'completed':
      return 'Afgewerkt'
    case 'Wachtend':
    case 'waitingOnOthers':
      return 'Wachtend'
    case 'Uitgesteld':
    case 'deferred':
      return 'Uitgesteld'
    default:
      return 'Open'
  }
}

const normalizePriority = (priority: string | undefined) => {
  switch (priority) {
    case 'Hoog':
    case 'high':
      return 'Hoog'
    case 'Normaal':
    case 'normal':
      return 'Normaal'
    case 'Laag':
    case 'low':
      return 'Laag'
    default:
      return 'Normaal'
  }
}

const deriveActionGroup = (action: Action) => {
  if (isWachtend(action)) return 'waiting'
  if (isVandaag(action)) return 'today'
  if (action.source === 'Outlook gemarkeerde mail' || /offerte|quotation|proposal/i.test(action.title)) return 'offers'
  if (isOpvolgen(action)) return 'urgent'
  return 'today'
}

  const mapMicrosoftAction = (item: MicrosoftActionResponse): Action => {
  const title = item.title ?? 'Onbekende actie'
  const dueDate = item.dueDate ?? ''
  const status = normalizeStatus(item.status)
    const action: Action = {
      id: item.id,
      priority: normalizePriority(item.priority),
      title,
      customer: item.customer ?? '',
      contact: item.contact ?? '',
      source: item.source ?? 'Microsoft To Do',
      dueDate,
      status,
      group: 'today',
      notes: item.notes ?? '',
      actionType: (item as any).actionType ?? '',
      webLink: item.webLink ?? '',
      microsoftList: item.microsoftList ?? '',
      lastModifiedDate: item.lastModifiedDate ?? '',
    }

  action.group = deriveActionGroup(action)
  return action
}

const isCompleted = (action: Action) => action.status === 'Afgewerkt'

// Vandaag: not completed, has dueDate, and dueDate <= today
// This also includes Wachtend items that have a dueDate <= today (they should appear in Vandaag)
const isVandaag = (action: Action) => {
  if (isCompleted(action)) return false
  if (!hasDueDate(action.dueDate)) return false
  const due = parseIsoToDate(action.dueDate)
  if (!due) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  due.setHours(0, 0, 0, 0)
  return due <= today
}

// Wachtend: not completed, status === 'Wachtend', and (no dueDate OR dueDate > today)
const isWachtend = (action: Action) => {
  if (isCompleted(action)) return false
  if (action.status !== 'Wachtend') return false
  if (!hasDueDate(action.dueDate)) return true
  const due = parseIsoToDate(action.dueDate)
  if (!due) return true
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  due.setHours(0, 0, 0, 0)
  return due > today
}

const isOffers = (_action: Action) => {
  // Open offertes is not supported yet — always zero and show no rows
  return false
}

// Opvolgen: not completed, status !== 'Wachtend', no dueDate, lastModifiedDate older than 14 days
const isOpvolgen = (action: Action) => {
  if (isCompleted(action)) return false
  if (action.status === 'Wachtend') return false
  if (hasDueDate(action.dueDate)) return false
  if (!action.lastModifiedDate) return false
  const lastMod = parseIsoToDate(action.lastModifiedDate)
  if (!lastMod) return false
  const cutoff = new Date()
  cutoff.setHours(0, 0, 0, 0)
  cutoff.setDate(cutoff.getDate() - 14)
  lastMod.setHours(0, 0, 0, 0)
  return lastMod <= cutoff
}

const matchesFilter = (action: Action, filter: string) => {
  switch (filter) {
    case 'today':
      return isVandaag(action)
    case 'waiting':
      return isWachtend(action)
    case 'offers':
      return isOffers(action)
    case 'urgent':
      return isOpvolgen(action)
    default:
      return true
  }
}

const Dashboard = () => {
  const [actions, setActions] = useState<Action[]>([])
  const [activeFilter, setActiveFilter] = useState<string>('all')
  const [showCompleted, setShowCompleted] = useState<boolean>(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingAction, setEditingAction] = useState<Action | null>(null)
  const [openDossierId, setOpenDossierId] = useState<string | null>(null)
  const [searchCustomer, setSearchCustomer] = useState('')

  useEffect(() => {
    let isMounted = true

    const loadActions = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetch('http://localhost:8000/actions', {
          headers: {
            Accept: 'application/json',
          },
        })

        if (!response.ok) {
          throw new Error('Microsoft actions could not be loaded.')
        }

        const payload: MicrosoftActionResponse[] = await response.json()
        if (!isMounted) return

        setActions(payload.map(mapMicrosoftAction))
      } catch (loadError) {
        if (!isMounted) return
        setError(loadError instanceof Error ? loadError.message : 'Microsoft actions could not be loaded.')
        setActions([])
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    loadActions()
    return () => {
      isMounted = false
    }
  }, [])

  // Reload actions when dossiers change elsewhere in the app
  useEffect(() => {
    const handler = () => {
      reloadActions()
    }
    window.addEventListener('dossiers:changed', handler as EventListener)
    return () => window.removeEventListener('dossiers:changed', handler as EventListener)
  }, [])

  // allow reloading after manual create/update
  const reloadActions = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('http://localhost:8000/actions', { headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error('Actions could not be loaded.')
      const payload: MicrosoftActionResponse[] = await response.json()
      setActions(payload.map(mapMicrosoftAction))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Actions could not be loaded.')
      setActions([])
    } finally {
      setLoading(false)
    }
  }

  const summaryCards = useMemo(
    () =>
      summaryCardDefinitions.map((card) => ({
        ...card,
        // exclude completed actions from card counts
        value: String(actions.filter((action) => !isCompleted(action) && matchesFilter(action, card.filter)).length),
      })),
    [actions],
  )

  const visibleActions = useMemo(() => {
    const list = activeFilter === 'all' ? actions : actions.filter((action) => matchesFilter(action, activeFilter))
    const filtered = showCompleted ? list.filter((a) => a.status === 'Afgewerkt') : list.filter((a) => a.status !== 'Afgewerkt')
    const q = searchCustomer.trim().toLowerCase()
    if (!q) return filtered
    return filtered.filter((a) => (a.customer ?? '').toLowerCase().includes(q))
  }, [actions, activeFilter, showCompleted, searchCustomer])

  return (
    <div className="app-shell">

      <main className="content">
        <DashboardCards
          cards={summaryCards}
          activeFilter={activeFilter}
          onSelectFilter={(filter) => setActiveFilter((current) => (current === filter ? 'all' : filter))}
        />

        <ActionTable
          actions={visibleActions}
          activeFilter={activeFilter}
          loading={loading}
          error={error}
          showCompleted={showCompleted}
          searchValue={searchCustomer}
          onSearchChange={(v) => setSearchCustomer(v)}
          onToggleCompleted={(value) => setShowCompleted(value)}
          onCreate={() => {
            setEditingAction(null)
            setShowCreateModal(true)
          }}
          onEdit={(action) => {
            // open dossier detail for Dossier source
            if (action.source === 'Dossier') {
              setOpenDossierId(action.id ?? null)
              return
            }

            // allow editing manual Command Center actions and limited edits for Microsoft/Outlook items
            if (action.source === 'Command Center' || action.source === 'Microsoft To Do' || action.source === 'Outlook gemarkeerde mail') {
              setEditingAction(action)
              setShowCreateModal(true)
            }
          }}
        />

        {showCreateModal && (
          <ManualActionModal
            initial={editingAction ?? undefined}
            onClose={() => {
              setShowCreateModal(false)
              setEditingAction(null)
            }}
            onSaved={() => {
              setShowCreateModal(false)
              setEditingAction(null)
              reloadActions()
            }}
          />
        )}
        {openDossierId && (
          <DossierDetail id={openDossierId} onClose={() => setOpenDossierId(null)} />
        )}
      </main>
    </div>
  )
}

export default Dashboard
