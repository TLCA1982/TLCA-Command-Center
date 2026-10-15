import { useState } from 'react'
import { apiUrl } from '../api'
import ContactPersonModal from './ContactPersonModal'

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
  const [draftContact, setDraftContact] = useState<any | null>(null)
  const [showContactModal, setShowContactModal] = useState(false)
  const [savedCompanyId, setSavedCompanyId] = useState<string | null>(null)
  const [attemptedContactName, setAttemptedContactName] = useState('')
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
      const companyId = company?.id ?? savedCompanyId
      const response = await fetch(apiUrl(companyId ? `/companies/${companyId}` : '/companies'), {
        method: companyId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ ...fields, relationship_type: fields.relationship_type || null }),
      })
      if (!response.ok) throw new Error((await response.text()) || 'Bedrijf opslaan mislukt')
      const savedCompany = await response.json()
      setSavedCompanyId(savedCompany.id)
      if (!company && draftContact) {
        // On retry, check whether the prior contact request already succeeded.
        let existingContact: any = null
        if (savedCompanyId) {
          const contactsResponse = await fetch(apiUrl(`/companies/${savedCompany.id}/contacts`))
          if (!contactsResponse.ok) throw new Error('Bedrijf is opgeslagen. Controleren van de contactpersoon mislukt; probeer opnieuw.')
          const contacts = await contactsResponse.json()
          existingContact = contacts.find((item: any) => item.name.trim().toLowerCase() === (attemptedContactName || draftContact.name).trim().toLowerCase())
        }
        if (existingContact) {
          if (draftContact.add_to_outlook && !existingContact.outlook_contact_id) {
            throw new Error('Bedrijf en contactpersoon zijn lokaal opgeslagen, maar de Outlook-koppeling ontbreekt nog. Vink toevoegen aan Outlook uit om af te ronden; de contactpersoon wordt niet dubbel aangemaakt.')
          }
        }
        setAttemptedContactName(draftContact.name)
        {
          const contactPath = `/companies/${savedCompany.id}/contacts${existingContact ? `/${existingContact.id}` : ''}`
          const contactResponse = await fetch(apiUrl(contactPath), {
            method: existingContact ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify(draftContact),
          })
          if (!contactResponse.ok) {
            const payload = await contactResponse.json().catch(() => null)
            throw new Error(`Bedrijf is opgeslagen. ${payload?.detail || 'Contactpersoon opslaan mislukt; probeer opnieuw.'}`)
          }
        }
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bedrijf opslaan mislukt')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>{company ? 'Bedrijf bewerken' : 'Bedrijf toevoegen'}</h3>
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
        {!company && <div className="detail-section">
          {draftContact && <p><strong>{draftContact.name}</strong>{draftContact.email && ` â€” ${draftContact.email}`}<br />Wordt samen met het bedrijf opgeslagen.</p>}
          <button type="button" className="action-btn action-btn--secondary" disabled={saving} onClick={() => setShowContactModal(true)}>{draftContact ? 'Contactpersoon bewerken' : '+ Contactpersoon toevoegen'}</button>
          {draftContact && !savedCompanyId && <button type="button" disabled={saving} onClick={() => setDraftContact(null)}>Verwijderen</button>}
        </div>}
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={saving}>Annuleren</button>
          <button type="button" onClick={() => save()} disabled={saving} className="action-btn action-btn--primary">Opslaan</button>
        </div>
      </div>
    </div>
    {showContactModal && <ContactPersonModal companyId="" contact={draftContact ?? undefined} allowOutlook prepareOnly onClose={() => setShowContactModal(false)} onSaved={setDraftContact} />}
    </>
  )
}

export default CompanyModal