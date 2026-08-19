import { useState } from 'react'
import { belgianToIso, isBelgianDate, isValidBelgianDate } from '../utils/date'
import { apiUrl } from '../api'

type Props = {
  onClose: () => void
  onSaved: () => void
}

const DossierModal = ({ onClose, onSaved }: Props) => {
  const [customer, setCustomer] = useState('')
  const [contact, setContact] = useState('')
  const [subject, setSubject] = useState('')
  const [status, setStatus] = useState('Lopend')
  const [followUp, setFollowUp] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async () => {
    if (!subject.trim()) {
      setError('Onderwerp is verplicht')
      return
    }
    setSaving(true)
    setError(null)

    let normalizedDate: string | undefined = ''
    if (followUp) {
      if (!isBelgianDate(followUp) || !isValidBelgianDate(followUp)) {
        setError('Ongeldige datum. Gebruik dd/mm/jjjj en zorg dat de datum bestaat.')
        setSaving(false)
        return
      }
      normalizedDate = belgianToIso(followUp)
    }

    const payload: any = {
      customer: customer.trim(),
      contact: contact.trim(),
      subject: subject.trim(),
      status,
      follow_up_date: normalizedDate,
    }

    try {
      const resp = await fetch(apiUrl('/dossiers'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) {
        const txt = await resp.text()
        throw new Error(txt || 'Failed to create dossier')
      }

      // Notify listeners that dossiers changed so the dashboard/actions can reload
      try {
        window.dispatchEvent(new CustomEvent('dossiers:changed'))
      } catch (_) {
        /* ignore */
      }

      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>Nieuw dossier</h3>

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

        {error && <p style={{ color: 'red' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" onClick={onClose} disabled={saving}>
            Annuleren
          </button>
          <button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">
            Dossier opslaan
          </button>
        </div>
      </div>
    </div>
  )
}

export default DossierModal
