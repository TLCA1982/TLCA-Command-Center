import { useEffect, useState } from 'react'
import { isoToBelgian, belgianToIso, isBelgianDate, isValidBelgianDate } from '../utils/date'
import DossierEventModal from './DossierEventModal'
import CompanyModal from './CompanyModal'
import ContactPersonModal from './ContactPersonModal'
import { apiUrl } from '../api'

type Props = { id: string; onClose: () => void }

const isPrimaryContact = (contact: any) => contact.is_primary === true || contact.is_primary === 1 || contact.is_primary === '1' || contact.is_primary === 'true'

const ContactSummary = ({ contact }: { contact: any }) => (
  <div className="contact-summary">
    <strong>{contact.name} {isPrimaryContact(contact) && <span className="contact-badge contact-badge--primary">Primair</span>} {!contact.is_active && <span className="contact-badge contact-badge--inactive">Inactief</span>}</strong>
    {contact.job_title && <span>{contact.job_title}</span>}
    {contact.email && <span>{contact.email}</span>}
    {contact.phone && <span>{contact.phone}</span>}
  </div>
)

const apiErrorMessage = async (response: Response, fallback: string) => {
  try {
    const payload = await response.json()
    return payload.detail || fallback
  } catch (_) {
    return (await response.text()) || fallback
  }
}

const DossierDetail = ({ id, onClose }: Props) => {
  const [data, setData] = useState<any | null>(null)
  const [companies, setCompanies] = useState<any[]>([])
  const [contacts, setContacts] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [showEventModal, setShowEventModal] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<any | null>(null)
  const [showCompanyModal, setShowCompanyModal] = useState(false)
  const [contactBeingEdited, setContactBeingEdited] = useState<any | undefined>(undefined)
  const [companyName, setCompanyName] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [primaryContactId, setPrimaryContactId] = useState('')
  const [subject, setSubject] = useState('')
  const [status, setStatus] = useState('Lopend')
  const [followUp, setFollowUp] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const response = await fetch(apiUrl(`/dossiers/${id}`), { headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error('Dossier kon niet geladen worden')
      setData(await response.json())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dossier kon niet geladen worden')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  useEffect(() => {
    fetch(apiUrl('/companies'), { headers: { Accept: 'application/json' } })
      .then(async (response) => { if (!response.ok) throw new Error('Bedrijven konden niet geladen worden'); setCompanies(await response.json()) })
      .catch((err) => setError(err instanceof Error ? err.message : 'Bedrijven konden niet geladen worden'))
  }, [])

  useEffect(() => {
    if (!data) return
    setCompanyId(data.company_id ?? '')
    setCompanyName(data.company?.name ?? data.customer ?? '')
    setPrimaryContactId(data.primary_contact_person_id ?? '')
    setSubject(data.subject ?? '')
    setStatus(data.status ?? 'Lopend')
    setFollowUp(data.follow_up_date ? isoToBelgian(data.follow_up_date) : '')
  }, [data])

  useEffect(() => {
    const activeCompanyId = data?.company_id ?? ''
    if (!activeCompanyId) {
      setCompanyId('')
      setContacts([])
      return
    }

    setCompanyId(activeCompanyId)
    fetch(apiUrl(`/companies/${activeCompanyId}/contacts`), { headers: { Accept: 'application/json' } })
      .then(async (response) => { if (!response.ok) throw new Error('Contactpersonen konden niet geladen worden'); setContacts(await response.json()) })
      .catch((err) => setError(err instanceof Error ? err.message : 'Contactpersonen konden niet geladen worden'))
  }, [data?.company_id])

  const selectableContacts = contacts.filter((contact) => contact.is_active || contact.id === primaryContactId)

  const selectCompany = (value: string) => {
    setCompanyName(value)
    const selected = companies.find((company) => company.name.toLowerCase() === value.trim().toLowerCase())
    setCompanyId(selected?.id ?? '')
    setPrimaryContactId('')
  }

  const save = async () => {
    if (!companies.some((company) => company.id === companyId)) { setError('Selecteer een bestaand bedrijf'); return }
    if (!subject.trim()) { setError('Onderwerp is verplicht'); return }
    if (followUp && (!isBelgianDate(followUp) || !isValidBelgianDate(followUp))) { setError('Ongeldige datum. Gebruik dd/mm/jjjj en zorg dat de datum bestaat.'); return }
    setSaving(true)
    setError(null)
    try {
      const response = await fetch(apiUrl(`/dossiers/${id}`), {
        method: 'PUT', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ company_id: companyId, ...(primaryContactId ? { primary_contact_person_id: primaryContactId } : {}), subject: subject.trim(), status, follow_up_date: followUp ? belgianToIso(followUp) : '' }),
      })
      if (!response.ok) throw new Error((await response.text()) || 'Opslaan mislukt')
      await load()
      setEditing(false)
      window.dispatchEvent(new CustomEvent('dossiers:changed'))
    } catch (err) { setError(err instanceof Error ? err.message : 'Opslaan mislukt')
    } finally { setSaving(false) }
  }

  const deleteContact = async (contact: any) => {
    if (!window.confirm(`Contactpersoon ${contact.name} verwijderen?`)) return
    try {
      const response = await fetch(apiUrl(`/companies/${companyId}/contacts/${contact.id}`), { method: 'DELETE', headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error(await apiErrorMessage(response, 'Contactpersoon verwijderen mislukt'))
      setContacts((current) => current.filter((item) => item.id !== contact.id))
      await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Contactpersoon verwijderen mislukt') }
  }

  const removeDossier = async () => {
    if (!window.confirm('Weet je zeker dat je dit dossier wilt verwijderen? Deze actie kan niet ongedaan worden gemaakt.')) return
    setSaving(true)
    setError(null)
    try {
      const response = await fetch(apiUrl(`/dossiers/${id}`), { method: 'DELETE', headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error((await response.text()) || 'Verwijderen mislukt')
      window.dispatchEvent(new CustomEvent('dossiers:changed'))
      onClose()
    } catch (err) { setError(err instanceof Error ? err.message : 'Verwijderen mislukt')
    } finally { setSaving(false) }
  }

  if (loading && !data) return <div className="modal-overlay"><div className="modal-card"><p>Laden...</p></div></div>

  return <div className="modal-overlay"><div className="modal-card dossier-detail-card">
    <h3>Dossier</h3>
    {error && <p className="form-error">{error}</p>}
    {data && <>
      {!editing ? <>
        <div className="detail-section"><div className="detail-section__heading"><h4>Bedrijf</h4><button type="button" className="action-btn action-btn--secondary" onClick={() => setShowCompanyModal(true)}>Bedrijf bewerken</button></div>
          <p className="detail-primary">{data.company?.name || data.customer}</p>
          {data.company?.relationship_type && <p>{data.company.relationship_type}</p>}
          {(data.company?.street || data.company?.house_number || data.company?.postal_code || data.company?.city || data.company?.country) && <p>{[data.company.street, data.company.house_number].filter(Boolean).join(' ')}{(data.company.street || data.company.house_number) && (data.company.postal_code || data.company.city) ? ', ' : ''}{[data.company.postal_code, data.company.city, data.company.country].filter(Boolean).join(' ')}</p>}
        </div>
        {data.primary_contact_person && <div className="detail-section"><h4>Primaire contactpersoon</h4><ContactSummary contact={data.primary_contact_person} /></div>}
        <p><strong>Onderwerp:</strong> {data.subject}</p><p><strong>Status:</strong> {data.status}</p><p><strong>Opvolgdatum:</strong> {data.follow_up_date ? isoToBelgian(data.follow_up_date) : ''}</p>
      </> : <>
        <label>Bedrijf<input list="detail-companies" value={companyName} onChange={(e) => selectCompany(e.target.value)} /><datalist id="detail-companies">{companies.map((company) => <option key={company.id} value={company.name} />)}</datalist></label>
        <label>Contactpersoon<select value={primaryContactId} onChange={(e) => setPrimaryContactId(e.target.value)} disabled={!companyId}><option value="">Geen primaire contactpersoon</option>{selectableContacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.name}{!contact.is_active ? ' (inactief)' : ''}</option>)}</select></label>
        <label>Onderwerp *<input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
        <label>Status<select value={status} onChange={(e) => setStatus(e.target.value)}><option>Lopend</option><option>Wachtend</option><option>Afgesloten</option></select></label>
        <label>Opvolgdatum<input type="text" placeholder="dd/mm/jjjj" value={followUp} onChange={(e) => setFollowUp(e.target.value)} /></label>
      </>}

      {companyId && <div className="detail-section contact-list"><div className="detail-section__heading"><h4>Contactpersonen</h4><button type="button" className="action-btn action-btn--secondary" onClick={() => setContactBeingEdited(null)}>Contactpersoon toevoegen</button></div>
        {contacts.length ? contacts.map((contact) => <div className="contact-row" key={contact.id}><ContactSummary contact={contact} /><div className="contact-row__actions"><button type="button" onClick={() => setContactBeingEdited(contact)}>Bewerken</button><button type="button" onClick={() => deleteContact(contact)}>Verwijderen</button></div></div>) : <p className="table-card__subtitle">Geen contactpersonen</p>}
      </div>}

      <div className="detail-section"><div className="detail-section__heading"><h4>Contactmomenten</h4><button className="action-btn action-btn--primary" onClick={() => setShowEventModal(true)}>+ Contactmoment toevoegen</button></div><div className="event-list">{data.events?.length ? data.events.map((event: any) => <div key={event.id} className="event-row" onClick={() => { setSelectedEvent(event); setShowEventModal(true) }}><div className="event-row__title">{isoToBelgian(event.event_date)} - {event.event_type}{event.contact_person?.name ? ` - ${event.contact_person.name}` : ''}</div><div className="event-row__notes">{event.notes}</div></div>) : <p>Geen contactmomenten</p>}</div></div>
    </>}
    <div className="modal-actions">{!editing ? <><button type="button" onClick={removeDossier} disabled={saving} className="danger-btn">Verwijderen</button><button type="button" onClick={() => setEditing(true)}>Bewerken</button><button type="button" onClick={onClose}>Sluiten</button></> : <><button type="button" onClick={() => { setEditing(false); setCompanyId(data.company_id ?? ''); setCompanyName(data.company?.name ?? data.customer ?? ''); setPrimaryContactId(data.primary_contact_person_id ?? ''); setSubject(data.subject ?? ''); setStatus(data.status ?? 'Lopend'); setFollowUp(data.follow_up_date ? isoToBelgian(data.follow_up_date) : '') }} disabled={saving}>Annuleren</button><button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">Dossier opslaan</button></>}</div>
    {showCompanyModal && data?.company && <CompanyModal company={data.company} onClose={() => setShowCompanyModal(false)} onSaved={load} />}
    {contactBeingEdited !== undefined && companyId && <ContactPersonModal allowOutlook companyId={companyId} contact={contactBeingEdited || undefined} onClose={() => setContactBeingEdited(undefined)} onSaved={async () => { setContactBeingEdited(undefined); const response = await fetch(apiUrl(`/companies/${companyId}/contacts`)); setContacts(await response.json()); await load() }} />}
    {showEventModal && <DossierEventModal dossierId={id} dossierCompanyId={data?.company_id ?? ''} currentStatus={data?.status} initialEvent={selectedEvent ?? undefined} onClose={() => { setShowEventModal(false); setSelectedEvent(null) }} onSaved={load} />}
  </div></div>
}

export default DossierDetail