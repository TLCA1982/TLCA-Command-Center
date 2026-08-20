import { useState, useEffect } from 'react'
import type { Action } from '../types/Action'
import { belgianToIso, isIsoDate, isBelgianDate, isValidBelgianDate, isoToBelgian } from '../utils/date'
import { apiUrl } from '../api'

type Props = {
  onClose: () => void
  onSaved: (action?: Action) => void
  initial?: Action
}

const ManualActionModal = ({ onClose, onSaved, initial }: Props) => {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [customer, setCustomer] = useState(initial?.customer ?? '')
  const [contact, setContact] = useState(initial?.contact ?? '')
  const [actionType, setActionType] = useState(initial?.actionType ?? 'Commerciële opvolging')
  const [priority, setPriority] = useState(initial?.priority ?? 'Normaal')
  const [dueDate, setDueDate] = useState(initial?.dueDate ? isoToBelgian(initial.dueDate) : '')
  const [status, setStatus] = useState(initial?.status ?? 'Open')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const typeOptions = [
    'Commerciële opvolging',
    'Technische opvolging',
    'Telefoongesprek',
    'Bezoek',
    'Administratief',
    'Andere',
  ]

  const priorityOptions = ['Hoog', 'Normaal', 'Laag']
  const statusOptions = ['Open', 'Wachtend', 'Uitgesteld', 'Afgewerkt']

  const save = async () => {
    if (!title.trim()) {
      setError('Titel is verplicht')
      return
    }
    setSaving(true)
    setError(null)

    // Normalize dueDate to ISO YYYY-MM-DD before sending.
    let normalizedDue: string | undefined = undefined
    if (dueDate) {
      // If user typed a Belgian date, validate it explicitly
      if (dueDate.includes('/')) {
        if (!isBelgianDate(dueDate) || !isValidBelgianDate(dueDate)) {
          setError('Ongeldige datum. Gebruik dd/mm/jjjj en zorg dat de datum bestaat.')
          setSaving(false)
          return
        }
        normalizedDue = belgianToIso(dueDate)
      } else if (isIsoDate(dueDate)) {
        normalizedDue = dueDate
      } else {
        setError('Ongeldige datum. Gebruik dd/mm/jjjj.')
        setSaving(false)
        return
      }
    }

    const payload = {
      title: title.trim(),
      customer,
      contact,
      type: actionType,
      priority,
      dueDate: normalizedDue,
      status,
      notes,
    }
    try {
      const isEdit = !!initial?.id
      if (isEdit && initial?.source && (initial.source === 'Microsoft To Do' || initial.source === 'Outlook gemarkeerde mail')) {
        // update Microsoft task via backend proxy endpoint
        const resp = await fetch(apiUrl(`/actions/microsoft/${initial.id}`), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ dueDate: normalizedDue, status, notes, customer, contact, actionType }),
        })

        if (!resp.ok) {
          const txt = await resp.text()
          throw new Error(txt || 'Failed to update Microsoft action')
        }
        onSaved(await resp.json())
      } else {
        const url = isEdit ? apiUrl(`/actions/manual/${initial?.id}`) : apiUrl('/actions/manual')
        const method = isEdit ? 'PUT' : 'POST'
        const resp = await fetch(url, {
          method,
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload),
        })
        if (!resp.ok) {
          const txt = await resp.text()
          throw new Error(txt || 'Failed to save')
        }
        onSaved(await resp.json())
      }

      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!initial?.id) return
    const ok = window.confirm('Weet je zeker dat je dit wilt verwijderen? Deze actie kan niet ongedaan worden gemaakt.')
    if (!ok) return
    setSaving(true)
    setError(null)
    try {
      const isMicrosoft = !!initial?.source && (initial.source === 'Microsoft To Do' || initial.source === 'Outlook gemarkeerde mail')
      const url = isMicrosoft ? apiUrl(`/actions/microsoft/${initial.id}`) : apiUrl(`/actions/manual/${initial.id}`)
      const resp = await fetch(url, { method: 'DELETE', headers: { Accept: 'application/json' } })
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || 'Verwijderen mislukt')
      }

      try { window.dispatchEvent(new CustomEvent('actions:changed')) } catch (_) {}
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verwijderen mislukt')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    // when initial prop changes (open for edit), populate state
    if (initial) {
      setTitle(initial.title ?? '')
      setCustomer(initial.customer ?? '')
      setContact(initial.contact ?? '')
      setActionType(initial.actionType ?? 'Commerciële opvolging')
      setPriority(initial.priority ?? 'Normaal')
      setDueDate(initial.dueDate ? isoToBelgian(initial.dueDate) : '')
      setStatus(initial.status ?? 'Open')
      setNotes(initial.notes ?? '')
    }
  }, [initial])

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>{initial ? (initial.source && (initial.source === 'Microsoft To Do' || initial.source === 'Outlook gemarkeerde mail') ? 'Microsoft actie bewerken' : 'Actie bewerken') : 'Nieuwe actie'}</h3>

        <label>
          Titel *
          <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={!!initial?.source && initial.source !== 'Command Center'} />
        </label>

        <label>
          Klant
          <input value={customer} onChange={(e) => setCustomer(e.target.value)} />
        </label>

        <label>
          Contactpersoon
          <input value={contact} onChange={(e) => setContact(e.target.value)} />
        </label>

        <label>
          Type
          <select value={actionType} onChange={(e) => setActionType(e.target.value)}>
            {typeOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <label>
          Prioriteit
          <select value={priority} onChange={(e) => setPriority(e.target.value)} disabled={!!initial?.source && initial.source !== 'Command Center'}>
            {priorityOptions.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>

        <label>
          Opvolgdatum
          <input
            type="text"
            placeholder="dd/mm/jjjj"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            pattern="[0-3][0-9]/[0-1][0-9]/[0-9]{4}"
          />
        </label>

        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label>
          Notitie
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          {initial?.id && (
            <button type="button" onClick={remove} disabled={saving} style={{ background: '#dc2626', color: '#fff' }}>
              Verwijderen
            </button>
          )}
          <button type="button" onClick={onClose} disabled={saving}>
            Annuleren
          </button>
          <button type="button" onClick={save} disabled={saving} style={{ background: '#2563eb', color: '#fff' }}>
            Actie opslaan
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManualActionModal
