import { useState, useEffect } from 'react'
import { belgianToIso, isoToBelgian, isBelgianDate, isValidBelgianDate } from '../utils/date'
import { apiUrl } from '../api'

type Props = {
  dossierId: string
  dossierCompanyId?: string
  currentStatus?: string
  onClose: () => void
  onSaved: () => void
  initialEvent?: any
}

const DossierEventModal = ({ dossierId, dossierCompanyId, currentStatus = 'Lopend', onClose, onSaved, initialEvent }: Props) => {
  const today = new Date()
  const dd = String(today.getDate()).padStart(2, '0')
  const mm = String(today.getMonth() + 1).padStart(2, '0')
  const yyyy = String(today.getFullYear())
  const [date, setDate] = useState(`${dd}/${mm}/${yyyy}`)
  const [type, setType] = useState('Notitie')
  const [notes, setNotes] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [status, setStatus] = useState(currentStatus)
  const [contactPersonId, setContactPersonId] = useState('')
  const [contactPersons, setContactPersons] = useState<any[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const editing = !!initialEvent?.id

  // populate fields when editing an existing event (useEffect to avoid setState during render)
  useEffect(() => {
    if (!dossierCompanyId) {
      setContactPersons([])
      setContactPersonId('')
      return
    }

    fetch(apiUrl(`/companies/${dossierCompanyId}/contacts`), { headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (!response.ok) throw new Error('Contactpersonen konden niet geladen worden')
        const items = await response.json()
        setContactPersons(items || [])
        setContactPersonId(initialEvent?.contact_person_id ?? '')
      })
      .catch(() => setError('Contactpersonen konden niet geladen worden'))
  }, [dossierCompanyId, initialEvent?.contact_person_id])

  useEffect(() => {
    if (!initialEvent) {
      setContactPersonId('')
      return
    }
    try {
      const e = initialEvent
      if (e.event_date) {
        const d = e.event_date
        const [y, m, ddv] = d.split('-')
        setDate(`${ddv}/${m}/${y}`)
      }
      if (e.event_type) setType(e.event_type)
      if (e.notes) setNotes(e.notes)
      if (e.follow_up_date) {
        setFollowUp(isoToBelgian(e.follow_up_date))
      }
      if (initialEvent.status_change) setStatus(initialEvent.status_change)
      setContactPersonId(e.contact_person_id ?? '')
    } catch (_) {
      // ignore parsing errors and keep defaults
    }
  }, [initialEvent])

  const save = async () => {
    if (!date || !type || !notes.trim()) {
      setError('Datum, Type en Notitie zijn verplicht')
      return
    }
    if (!isBelgianDate(date) || !isValidBelgianDate(date)) {
      setError('Ongeldige datum. Gebruik dd/mm/jjjj')
      return
    }

    let normalizedDate = belgianToIso(date)
    let normalizedFollow: string | undefined = undefined
    if (followUp) {
      if (!isBelgianDate(followUp) || !isValidBelgianDate(followUp)) {
        setError('Ongeldige opvolgdatum. Gebruik dd/mm/jjjj')
        return
      }
      normalizedFollow = belgianToIso(followUp)
    }

    const payload: any = {
      event_date: normalizedDate,
      event_type: type,
      notes: notes.trim(),
    }
    if (normalizedFollow) payload['follow_up_date'] = normalizedFollow
    if (status && status !== currentStatus) payload['status_change'] = status
    if (contactPersonId) payload['contact_person_id'] = contactPersonId
    else if (editing && initialEvent?.contact_person_id) payload['contact_person_id'] = null

    setSaving(true)
    setError(null)
    try {
      let resp: Response
      if (editing) {
        resp = await fetch(apiUrl(`/dossiers/${dossierId}/events/${initialEvent.id}`), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload),
        })
      } else {
        resp = await fetch(apiUrl(`/dossiers/${dossierId}/events`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload),
        })
      }
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || 'Failed to add event')
      }

      // notify other components
      try { window.dispatchEvent(new CustomEvent('dossiers:changed')) } catch (_) {}

      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!editing || !initialEvent?.id) return
    const ok = window.confirm('Weet je zeker dat je dit contactmoment wilt verwijderen? Deze actie kan niet ongedaan worden gemaakt.')
    if (!ok) return
    setSaving(true)
    setError(null)
    try {
      const resp = await fetch(apiUrl(`/dossiers/${dossierId}/events/${initialEvent.id}`), { method: 'DELETE', headers: { Accept: 'application/json' } })
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || 'Verwijderen mislukt')
      }
      try { window.dispatchEvent(new CustomEvent('dossiers:changed')) } catch (_) {}
      onSaved()
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
        <h3>{editing ? 'Contactmoment bewerken' : 'Nieuw contactmoment'}</h3>

        <label>
          Datum *
          <input value={date} onChange={(e) => setDate(e.target.value)} placeholder="dd/mm/jjjj" />
        </label>

        <label>
          Type *
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option>Bezoek</option>
            <option>Telefoon</option>
            <option>E-mail</option>
            <option>Notitie</option>
            <option>Test</option>
            <option>Andere</option>
          </select>
        </label>

        <label>
          Notitie *
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <label>
          Nieuwe opvolgdatum
          <input value={followUp} onChange={(e) => setFollowUp(e.target.value)} placeholder="dd/mm/jjjj" />
        </label>

        {dossierCompanyId && (
          <label>
            Contactpersoon
            <select value={contactPersonId} onChange={(e) => setContactPersonId(e.target.value)} disabled={!dossierCompanyId || !contactPersons.length}>
              <option value="">Geen contactpersoon</option>
              {contactPersons.map((contact) => (
                <option key={contact.id} value={contact.id}>{contact.name}</option>
              ))}
            </select>
          </label>
        )}

        <label>
          Status dossier
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="Lopend">Lopend</option>
            <option value="Wachtend">Wachtend</option>
            <option value="Afgesloten">Afgesloten</option>
          </select>
        </label>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          {editing && (
            <button type="button" onClick={remove} disabled={saving} style={{ background: '#dc2626', color: '#fff' }}>Verwijderen</button>
          )}
          <button type="button" onClick={onClose} disabled={saving}>Annuleren</button>
          <button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">Contactmoment opslaan</button>
        </div>
      </div>
    </div>
  )
}

export default DossierEventModal
