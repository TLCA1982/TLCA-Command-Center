import { useEffect, useState } from 'react'
// Header is rendered at the app root now
import DossierDetail from '../components/DossierDetail'
import { isoToBelgian } from '../utils/date'
import DossierModal from '../components/DossierModal'
import { apiUrl } from '../api'

const Dossiers = () => {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openDossierId, setOpenDossierId] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  const sortFields: Record<string, (dossier: any) => string> = {
    last_activity: (dossier) => dossier.last_activity ?? dossier.created_at ?? '',
    customer: (dossier) => dossier.customer ?? '',
    contact: (dossier) => dossier.contact ?? '',
    subject: (dossier) => dossier.subject ?? '',
    last_contact: () => '',
    status: (dossier) => dossier.status ?? '',
    follow_up_date: (dossier) => dossier.follow_up_date ?? '',
    source: (dossier) => dossier.source ?? 'Dossier',
  }

  const handleSort = (nextSortKey: string) => {
    if (sortKey === nextSortKey) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(nextSortKey)
    setSortDirection('asc')
  }

  const sortableHeader = (key: string, label: string) => (
    <button
      type="button"
      onClick={() => handleSort(key)}
      style={{ border: 0, background: 'none', padding: 0, font: 'inherit', color: 'inherit', cursor: 'pointer' }}
      aria-label={`Sorteer op ${label}`}
    >
      {label}
      {sortKey === key && <span aria-hidden="true" style={{ marginLeft: 4, opacity: 0.65 }}>{sortDirection === 'asc' ? '▲' : '▼'}</span>}
    </button>
  )

  useEffect(() => {
    let mounted = true
    const load = async () => {
      setLoading(true)
      try {
        const resp = await fetch(apiUrl('/dossiers'), { headers: { Accept: 'application/json' } })
        if (!resp.ok) throw new Error('Dossiers konden niet geladen worden')
        const payload = await resp.json()
        if (!mounted) return
        setItems(payload)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Fout')
      } finally {
        setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [])

  const reload = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(apiUrl('/dossiers'), { headers: { Accept: 'application/json' } })
      if (!resp.ok) throw new Error('Dossiers konden niet geladen worden')
      const payload = await resp.json()
      setItems(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fout')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const listener = () => reload()
    window.addEventListener('dossiers:changed', listener as EventListener)
    return () => window.removeEventListener('dossiers:changed', listener as EventListener)
  }, [])

  return (
    <div className="app-shell">

      <main className="content">
        <div className="table-card">
          <div className="table-card__header">
            <div>
              <h2>Dossiers</h2>
              <div style={{ marginTop: 8 }}>
                <input
                  placeholder="Zoeken op klant..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid #e2e8f0', width: 260 }}
                />
              </div>
            </div>
            <div>
              <button className="action-btn action-btn--primary" onClick={() => setShowCreateModal(true)}>
                + Nieuw dossier
              </button>
            </div>
          </div>
          {loading ? (
            <div className="table-wrapper"><p className="table-card__subtitle">Laden...</p></div>
          ) : error ? (
            <div className="table-wrapper"><p className="table-card__subtitle" style={{ color: 'red' }}>{error}</p></div>
          ) : (
            <div className="table-wrapper">
              {(() => {
                const filteredItems = items.filter((d) => {
                const q = search.trim().toLowerCase()
                if (!q) return true
                return (d.customer || '').toLowerCase().includes(q)
                })
                const visibleItems = sortKey ? [...filteredItems].sort((left, right) => {
                  const leftValue = sortFields[sortKey](left)
                  const rightValue = sortFields[sortKey](right)
                  if (!leftValue && rightValue) return 1
                  if (leftValue && !rightValue) return -1
                  if (!leftValue && !rightValue) return 0
                  const comparison = sortKey === 'last_activity' || sortKey === 'follow_up_date'
                    ? leftValue.localeCompare(rightValue)
                    : leftValue.localeCompare(rightValue, undefined, { sensitivity: 'base' })
                  return sortDirection === 'asc' ? comparison : -comparison
                }) : filteredItems

                return visibleItems.length === 0 ? (
                <p className="table-card__subtitle">Geen dossiers gevonden voor deze klant.</p>
              ) : (
              <table>
                <thead>
                  <tr>
                    <th>{sortableHeader('last_activity', 'Laatste activiteit')}</th>
                    <th>{sortableHeader('customer', 'Klant')}</th>
                    <th>{sortableHeader('contact', 'Contactpersoon')}</th>
                    <th>{sortableHeader('subject', 'Onderwerp')}</th>
                    <th>{sortableHeader('last_contact', 'Laatste contact')}</th>
                    <th>{sortableHeader('status', 'Status')}</th>
                    <th>{sortableHeader('follow_up_date', 'Opvolgdatum')}</th>
                    <th>{sortableHeader('source', 'Bron')}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((d) => (
                    <tr key={d.id} onClick={() => setOpenDossierId(d.id)} style={{ cursor: 'pointer' }}>
                          <td>{isoToBelgian(d.last_activity ?? d.created_at ?? '')}</td>
                          <td>{d.customer}</td>
                          <td>{d.contact}</td>
                          <td>{d.subject}</td>
                          <td>{/* last contact type could be derived later */}</td>
                          <td>{d.status}</td>
                          <td>{d.follow_up_date ? isoToBelgian(d.follow_up_date) : ''}</td>
                          <td>{d.source ?? 'Dossier'}</td>
                        </tr>
                  ))}
                </tbody>
              </table>
              )
              })()}
            </div>
          )}
        </div>
      </main>

      {openDossierId && <DossierDetail id={openDossierId} onClose={() => setOpenDossierId(null)} />}
      {showCreateModal && (
        <DossierModal
          onClose={() => setShowCreateModal(false)}
          onSaved={() => {
            setShowCreateModal(false)
            reload()
          }}
        />
      )}
    </div>
  )
}

export default Dossiers
