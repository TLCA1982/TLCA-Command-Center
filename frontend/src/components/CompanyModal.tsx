import { useState } from 'react'
import { apiUrl } from '../api'

type Props = {
  company?: any
  onClose: () => void
  onSaved: () => void
}

const CompanyModal = ({ company, onClose, onSaved }: Props) => {
  const [fields, setFields] = useState({
    name: company?.name ?? '',
    relationship_type: company?.relationship_type ?? '',
    street: company?.street ?? '',
    house_number: company?.house_number ?? '',
    postal_code: company?.postal_code ?? '',
    city: company?.city ?? '',
    country: company?.country ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setField = (field: string, value: string) => setFields((current) => ({ ...current, [field]: value }))

  const save = async () => {
    if (!fields.name.trim()) {
      setError('Bedrijfsnaam is verplicht')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const response = await fetch(apiUrl(company ? `/companies/${company.id}` : '/companies'), {
        method: company ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ ...fields, relationship_type: fields.relationship_type || null }),
      })
      if (!response.ok) throw new Error((await response.text()) || 'Bedrijf opslaan mislukt')
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bedrijf opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>Bedrijf bewerken</h3>
        <label>Bedrijfsnaam<input value={fields.name} onChange={(e) => setField('name', e.target.value)} /></label>
        <label>Relatie<select value={fields.relationship_type} onChange={(e) => setField('relationship_type', e.target.value)}>
          <option value="">Niet ingesteld</option>
          <option value="Klant">Klant</option>
          <option value="Prospect">Prospect</option>
          <option value="Leverancier">Leverancier</option>
        </select></label>
        <div className="form-grid form-grid--address">
          <label>Straat<input value={fields.street} onChange={(e) => setField('street', e.target.value)} /></label>
          <label>Huisnummer<input value={fields.house_number} onChange={(e) => setField('house_number', e.target.value)} /></label>
          <label>Postcode<input value={fields.postal_code} onChange={(e) => setField('postal_code', e.target.value)} /></label>
          <label>Stad<input value={fields.city} onChange={(e) => setField('city', e.target.value)} /></label>
        </div>
        <label>Land<input value={fields.country} onChange={(e) => setField('country', e.target.value)} /></label>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={saving}>Annuleren</button>
          <button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">Opslaan</button>
        </div>
      </div>
    </div>
  )
}

export default CompanyModal