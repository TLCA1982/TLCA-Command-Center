import { useEffect, useState } from 'react'
import { belgianToIso, isBelgianDate, isValidBelgianDate } from '../utils/date'
import { apiUrl } from '../api'

type Props = {
  onClose: () => void
  onSaved: () => void
}

const DossierModal = ({ onClose, onSaved }: Props) => {
  const [companies, setCompanies] = useState<any[]>([])
  const [companyName, setCompanyName] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [contacts, setContacts] = useState<any[]>([])
  const [primaryContactId, setPrimaryContactId] = useState('')
  const [subject, setSubject] = useState('')
  const [status, setStatus] = useState('Lopend')
  const [followUp, setFollowUp] = useState('')
  const [saving, setSaving] = useState(false)
  const [loadingCompanies, setLoadingCompanies] = useState(true)
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadCompanies = async () => {
      try {
        const response = await fetch(apiUrl('/companies'), { headers: { Accept: 'application/json' } })
        if (!response.ok) throw new Error('Bedrijven konden niet geladen worden')
        setCompanies(await response.json())
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Bedrijven konden niet geladen worden')
      } finally {
        setLoadingCompanies(false)
      }
    }
    loadCompanies()
  }, [])

  useEffect(() => {
    if (!companyId) {
      setContacts([])
      setPrimaryContactId('')
      return
    }
    const loadContacts = async () => {
      setLoadingContacts(true)
      try {
        const response = await fetch(apiUrl(`/companies/${companyId}/contacts`), { headers: { Accept: 'application/json' } })
        if (!response.ok) throw new Error('Contactpersonen konden niet geladen worden')
        setContacts(await response.json())
      } catch (err) {
        setContacts([])
        setError(err instanceof Error ? err.message : 'Contactpersonen konden niet geladen worden')
      } finally {
        setLoadingContacts(false)
      }
    }
    loadContacts()
  }, [companyId])

  const selectCompany = (value: string) => {
    setCompanyName(value)
    const selected = companies.find((company) => company.name.toLowerCase() === value.trim().toLowerCase())
    setCompanyId(selected?.id ?? '')
    setPrimaryContactId('')
  }

  const activeContacts = contacts.filter((contact) => contact.is_active)

  const save = async () => {
    const selectedCompany = companies.find((company) => company.id === companyId)
    if (!selectedCompany) {
      setError('Selecteer een bestaand bedrijf')
      return
    }
    if (!subject.trim()) {
      setError('Onderwerp is verplicht')
      return
    }
    setSaving(true)
    setError(null)

    let normalizedDate = ''
    if (followUp) {
      if (!isBelgianDate(followUp) || !isValidBelgianDate(followUp)) {
        setError('Ongeldige datum. Gebruik dd/mm/jjjj en zorg dat de datum bestaat.')
        setSaving(false)
        return
      }
      normalizedDate = belgianToIso(followUp)
    }

    try {
      const response = await fetch(apiUrl('/dossiers'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          ...(primaryContactId ? { primary_contact_person_id: primaryContactId } : {}),
          subject: subject.trim(),
          status,
          follow_up_date: normalizedDate,
        }),
      })
      if (!response.ok) throw new Error((await response.text()) || 'Dossier opslaan mislukt')
      try { window.dispatchEvent(new CustomEvent('dossiers:changed')) } catch (_) {}
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
        <label>Bedrijf
          <input list="dossier-companies" value={companyName} onChange={(e) => selectCompany(e.target.value)} placeholder="Zoek bedrijf..." disabled={loadingCompanies} />
          <datalist id="dossier-companies">{companies.map((company) => <option key={company.id} value={company.name} />)}</datalist>
        </label>
        <label>Contactpersoon
          <select value={primaryContactId} onChange={(e) => setPrimaryContactId(e.target.value)} disabled={!companyId || loadingContacts}>
            <option value="">Geen primaire contactpersoon</option>
            {activeContacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.name}</option>)}
          </select>
        </label>
        <label>Onderwerp *<input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
        <label>Status<select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="Lopend">Lopend</option>
          <option value="Wachtend">Wachtend</option>
          <option value="Afgesloten">Afgesloten</option>
        </select></label>
        <label>Opvolgdatum<input type="text" placeholder="dd/mm/jjjj" value={followUp} onChange={(e) => setFollowUp(e.target.value)} /></label>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={saving}>Annuleren</button>
          <button type="button" onClick={save} disabled={saving} className="action-btn action-btn--primary">Dossier opslaan</button>
        </div>
      </div>
    </div>
  )
}

export default DossierModal