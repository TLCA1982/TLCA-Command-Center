import { useState, useEffect } from 'react'
import { isoToBelgian, belgianToIso, isBelgianDate, isValidBelgianDate } from '../utils/date'
import DossierEventModal from './DossierEventModal'

type Props = {
  id: string
  onClose: () => void
}

const DossierDetail = ({ id, onClose }: Props) => {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [showEventModal, setShowEventModal] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<any | null>(null)
  const [customer, setCustomer] = useState('')
  const [contact, setContact] = useState('')
  const [subject, setSubject] = useState('')
  const [status, setStatus] = useState('Lopend')
  const [followUp, setFollowUp] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`http://localhost:8000/dossiers/${id}`, { headers: { Accept: 'application/json' } })
      if (!resp.ok) throw new Error('Dossier kon niet geladen worden')
      const payload = await resp.json()
      setData(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fout')
    } finally {
      setLoading(false)
    }
  }

  if (!data && !loading) load()

  useEffect(() => {
    if (data) {
      setCustomer(data.customer ?? '')
      setContact(data.contact ?? '')
      setSubject(data.subject ?? '')
      setStatus(data.status ?? 'Lopend')
      setFollowUp(data.follow_up_date ? isoToBelgian(data.follow_up_date) : '')
    }
  }, [data])

  const save = async () => {
    setSaving(true)
    setError(null)
    if (!subject.trim()) {
      setError('Onderwerp is verplicht')
      setSaving(false)
      return
    }

    let normalized: string | undefined = ''
    if (followUp) {
      if (!isBelgianDate(followUp) || !isValidBelgianDate(followUp)) {
        setError('Ongeldige datum. Gebruik dd/mm/jjjj en zorg dat de datum bestaat.')
        setSaving(false)
        return
      }
      normalized = belgianToIso(followUp)
    }

    const payload: any = {
      customer: customer.trim(),
      contact: contact.trim(),
      subject: subject.trim(),
      status,
      follow_up_date: normalized,
    }

    try {
      const resp = await fetch(`http://localhost:8000/dossiers/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || 'Opslaan mislukt')
      }

      await load()
      try { window.dispatchEvent(new CustomEvent('dossiers:changed')) } catch (_) {}
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    const ok = window.confirm('Weet je zeker dat je dit wilt verwijderen? Deze actie kan niet ongedaan worden gemaakt.')
    if (!ok) return
    setSaving(true)
    setError(null)
    try {
      const resp = await fetch(`http://localhost:8000/dossiers/${id}`, { method: 'DELETE', headers: { Accept: 'application/json' } })
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || 'Verwijderen mislukt')
      }
      try { window.dispatchEvent(new CustomEvent('dossiers:changed')) } catch (_) {}
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verwijderen mislukt')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>Dossier</h3>
        {loading && <p>Laden...</p>}
        {error && <p style={{ color: 'red' }}>{error}</p>}
        {data && (
          <div>
            {!editing ? (
              <>
                <p><strong>Klant:</strong> {data.customer}</p>
                <p><strong>Contactpersoon:</strong> {data.contact}</p>
                <p><strong>Onderwerp:</strong> {data.subject}</p>
                <p><strong>Status:</strong> {data.status}</p>
                <p><strong>Opvolgdatum:</strong> {data.follow_up_date ? isoToBelgian(data.follow_up_date) : ''}</p>
              </>
            ) : (
              <>
                <label>
                  Klant
                  <input value={customer} onChange={(e) => setCustomer(e.target.value)} />
                </label>
                <label>
                  Contactpersoon
                  <input value={contact} onChange={(e) => setContact(e.target.value)} />
                </label>
                <label>
                  Onderwerp *
                  <input value={subject} onChange={(e) => setSubject(e.target.value)} />
                </label>
                <label>
                  Status
                  <select value={status} onChange={(e) => setStatus(e.target.value)}>
                    <option value="Lopend">Lopend</option>
                    <option value="Wachtend">Wachtend</option>
                    <option value="Afgesloten">Afgesloten</option>
                  </select>
                </label>
                <label>
                  Opvolgdatum
                  <input type="text" placeholder="dd/mm/jjjj" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
                </label>
              </>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4>Contactmomenten</h4>
              <div>
                <button className="action-btn action-btn--primary" onClick={() => setShowEventModal(true)}>+ Contactmoment toevoegen</button>
              </div>
            </div>
            <div style={{ maxHeight: 240, overflow: 'auto' }}>
              {data.events && data.events.length ? (
                data.events.map((e: any) => (
                  <div key={e.id} style={{ marginBottom: 8, cursor: 'pointer' }} onClick={() => { setSelectedEvent(e); setShowEventModal(true); }}>
                    <div style={{ fontWeight: 600 }}>{isoToBelgian(e.event_date)} - {e.event_type}</div>
                    <div style={{ color: '#64748b' }}>{e.notes}</div>
                  </div>
                ))
              ) : (
                <p>Geen contactmomenten</p>
              )}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          {!editing ? (
            <>
              <button type="button" onClick={remove} disabled={saving} style={{ background: '#dc2626', color: '#fff' }}>Verwijderen</button>
              <button type="button" onClick={() => setEditing(true)}>Bewerken</button>
              <button type="button" onClick={onClose}>Sluiten</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => { setEditing(false); /* reset to loaded values */ setCustomer(data.customer ?? ''); setContact(data.contact ?? ''); setSubject(data.subject ?? ''); setStatus(data.status ?? 'Lopend'); setFollowUp(data.follow_up_date ? isoToBelgian(data.follow_up_date) : ''); }} disabled={saving}>Annuleren</button>
              <button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">Dossier opslaan</button>
            </>
          )}
        </div>
        {showEventModal && (
          <DossierEventModal
            dossierId={id}
            currentStatus={data?.status}
            initialEvent={selectedEvent ?? undefined}
            onClose={() => { setShowEventModal(false); setSelectedEvent(null); }}
            onSaved={() => {
              // reload detail but keep modal closed and detail open
              load()
            }}
          />
        )}
      </div>
    </div>
  )
}

export default DossierDetail
