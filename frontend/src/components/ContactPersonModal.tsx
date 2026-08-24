import { useState } from 'react'
import { apiUrl } from '../api'

type Props = {
  companyId: string
  contact?: any
  allowOutlook?: boolean
  onClose: () => void
  onSaved: (contact?: any) => void
}

const toBoolean = (value: unknown, fallback: boolean) => {
  if (typeof value === 'boolean') return value
  if (value === 1 || value === '1' || value === 'true') return true
  if (value === 0 || value === '0' || value === 'false') return false
  return fallback
}

const ContactPersonModal = ({ companyId, contact, allowOutlook = false, onClose, onSaved }: Props) => {
  const [fields, setFields] = useState({
    name: contact?.name ?? '',
    email: contact?.email ?? '',
    phone: contact?.phone ?? '',
    mobile_phone: contact?.mobile_phone ?? '',
    job_title: contact?.job_title ?? '',
    is_active: toBoolean(contact?.is_active, true),
    is_primary: toBoolean(contact?.is_primary, false),
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [addToOutlook, setAddToOutlook] = useState(false)
  const setField = (field: string, value: string | boolean) => setFields((current) => ({ ...current, [field]: value }))

  const save = async () => {
    if (!fields.name.trim()) {
      setError('Naam is verplicht')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const response = await fetch(apiUrl(contact ? `/companies/${companyId}/contacts/${contact.id}` : `/companies/${companyId}/contacts`), {
        method: contact ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ ...fields, ...(allowOutlook && !contact ? { add_to_outlook: addToOutlook } : {}) }),
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        throw new Error(payload?.detail || 'Contactpersoon opslaan mislukt')
      }
      onSaved(await response.json())
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Contactpersoon opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>{contact ? 'Contactpersoon bewerken' : 'Contactpersoon toevoegen'}</h3>
        <label>Naam<input value={fields.name} onChange={(e) => setField('name', e.target.value)} /></label>
        <label>Functie<input value={fields.job_title} onChange={(e) => setField('job_title', e.target.value)} /></label>
        <label>E-mail<input type="email" value={fields.email} onChange={(e) => setField('email', e.target.value)} /></label>
        <label>Telefoon<input value={fields.phone} onChange={(e) => setField('phone', e.target.value)} /></label>
        <label>Mobiel<input value={fields.mobile_phone} onChange={(e) => setField('mobile_phone', e.target.value)} /></label>
        <label className="checkbox-field"><input type="checkbox" checked={fields.is_active} onChange={(e) => setFields((current) => ({ ...current, is_active: e.target.checked, is_primary: e.target.checked && current.is_primary }))} />Actief</label>
        <label className="checkbox-field"><input type="checkbox" checked={fields.is_primary} disabled={!fields.is_active} onChange={(e) => setField('is_primary', e.target.checked)} />Primair contact</label>
        {allowOutlook && !contact && <label className="checkbox-field"><input type="checkbox" checked={addToOutlook} onChange={(e) => setAddToOutlook(e.target.checked)} />Ook toevoegen aan Outlook</label>}
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={saving}>Annuleren</button>
          <button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">Opslaan</button>
        </div>
      </div>
    </div>
  )
}

export default ContactPersonModal