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
              {items.filter((d) => {
                const q = search.trim().toLowerCase()
                if (!q) return true
                return (d.customer || '').toLowerCase().includes(q)
              }).length === 0 ? (
                <p className="table-card__subtitle">Geen dossiers gevonden voor deze klant.</p>
              ) : (
              <table>
                <thead>
                  <tr>
                    <th>Laatste activiteit</th>
                    <th>Klant</th>
                    <th>Contactpersoon</th>
                    <th>Onderwerp</th>
                    <th>Laatste contact</th>
                    <th>Status</th>
                    <th>Opvolgdatum</th>
                    <th>Bron</th>
                  </tr>
                </thead>
                <tbody>
                  {items
                    .filter((d) => {
                      const q = search.trim().toLowerCase()
                      if (!q) return true
                      return (d.customer || '').toLowerCase().includes(q)
                    })
                    .map((d) => (
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
              )}
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
