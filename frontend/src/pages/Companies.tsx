import { useEffect, useState } from 'react'
import CompanyModal from '../components/CompanyModal'
import ContactPersonModal from '../components/ContactPersonModal'
import { apiUrl } from '../api'

const Companies = () => {
  const [companies, setCompanies] = useState<any[]>([])
  const [selectedCompany, setSelectedCompany] = useState<any | null>(null)
  const [contacts, setContacts] = useState<any[]>([])
  const [contactBeingEdited, setContactBeingEdited] = useState<any | undefined>(undefined)
  const [showCompanyModal, setShowCompanyModal] = useState(false)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadCompanies = async () => {
    setLoading(true)
    try {
      const response = await fetch(apiUrl('/companies'), { headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error('Bedrijven konden niet geladen worden')
      setCompanies(await response.json())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bedrijven konden niet geladen worden')
    } finally {
      setLoading(false)
    }
  }

  const loadContacts = async (companyId: string) => {
    try {
      const response = await fetch(apiUrl(`/companies/${companyId}/contacts`), { headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error('Contactpersonen konden niet geladen worden')
      setContacts(await response.json())
    } catch (err) {
      setContacts([])
      setError(err instanceof Error ? err.message : 'Contactpersonen konden niet geladen worden')
    }
  }

  useEffect(() => { loadCompanies() }, [])

  const openCompany = (company: any) => {
    setSelectedCompany(company)
    setContactBeingEdited(undefined)
    loadContacts(company.id)
  }

  const refreshCompany = async () => {
    await loadCompanies()
    if (!selectedCompany) return
    const response = await fetch(apiUrl(`/companies/${selectedCompany.id}`), { headers: { Accept: 'application/json' } })
    if (response.ok) setSelectedCompany(await response.json())
  }

  const filteredCompanies = companies.filter((company) => company.name.toLowerCase().includes(search.trim().toLowerCase()))

  return (
    <div className="app-shell">
      <main className="content">
        <div className="table-card">
          <div className="table-card__header">
            <div>
              <h2>Bedrijven</h2>
              <div style={{ marginTop: 8 }}>
                <input placeholder="Zoeken op bedrijfsnaam..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ padding: '6px 8px', borderRadius: 8, border: '1px solid #e2e8f0', width: 260 }} />
              </div>
            </div>
            <button type="button" className="action-btn action-btn--primary" onClick={() => setShowCompanyModal(true)}>+ Nieuw bedrijf</button>
          </div>
          {loading ? <p className="table-card__subtitle">Laden...</p> : error ? <p className="table-card__subtitle" style={{ color: 'red' }}>{error}</p> : (
            <div className="table-wrapper">
              {filteredCompanies.length ? <table><thead><tr><th>Bedrijf</th><th>Relatie</th><th>Stad</th><th>Acties</th></tr></thead><tbody>
                {filteredCompanies.map((company) => <tr key={company.id} onClick={() => openCompany(company)} style={{ cursor: 'pointer' }}><td>{company.name}</td><td>{company.relationship_type || 'Niet ingesteld'}</td><td>{company.city}</td><td><button type="button" onClick={(event) => { event.stopPropagation(); openCompany(company) }}>Openen</button></td></tr>)}
              </tbody></table> : <p className="table-card__subtitle">Geen bedrijven gevonden.</p>}
            </div>
          )}
        </div>
      </main>

      {showCompanyModal && !selectedCompany && <CompanyModal onClose={() => setShowCompanyModal(false)} onSaved={async () => { setShowCompanyModal(false); await loadCompanies() }} />}
      {selectedCompany && <div className="modal-overlay"><div className="modal-card dossier-detail-card">
        <div className="detail-section__heading"><h3>{selectedCompany.name}</h3><button type="button" onClick={() => setSelectedCompany(null)}>Sluiten</button></div>
        {selectedCompany.relationship_type && <p>{selectedCompany.relationship_type}</p>}
        {(selectedCompany.street || selectedCompany.house_number || selectedCompany.postal_code || selectedCompany.city || selectedCompany.country) && <p>{[selectedCompany.street, selectedCompany.house_number].filter(Boolean).join(' ')}{(selectedCompany.street || selectedCompany.house_number) && (selectedCompany.postal_code || selectedCompany.city) ? ', ' : ''}{[selectedCompany.postal_code, selectedCompany.city, selectedCompany.country].filter(Boolean).join(' ')}</p>}
        <div className="detail-section contact-list"><div className="detail-section__heading"><h4>Contactpersonen</h4><button type="button" className="action-btn action-btn--secondary" onClick={() => setContactBeingEdited(null)}>Contactpersoon toevoegen</button></div>
          {contacts.length ? contacts.map((contact) => <div className="contact-row" key={contact.id}><div className="contact-summary"><strong>{contact.name} {contact.is_primary && <span className="contact-badge contact-badge--primary">Primair</span>} {!contact.is_active && <span className="contact-badge contact-badge--inactive">Inactief</span>}</strong>{contact.job_title && <span>{contact.job_title}</span>}{contact.email && <span>{contact.email}</span>}{contact.phone && <span>{contact.phone}</span>}{contact.mobile_phone && <span>{contact.mobile_phone}</span>}</div><div className="contact-row__actions"><button type="button" onClick={() => setContactBeingEdited(contact)}>Bewerken</button></div></div>) : <p className="table-card__subtitle">Geen contactpersonen</p>}
        </div>
        <div className="modal-actions"><button type="button" onClick={() => setShowCompanyModal(true)}>Bedrijf bewerken</button></div>
        {contactBeingEdited !== undefined && <ContactPersonModal allowOutlook companyId={selectedCompany.id} contact={contactBeingEdited || undefined} onClose={() => setContactBeingEdited(undefined)} onSaved={async () => { setContactBeingEdited(undefined); await loadContacts(selectedCompany.id) }} />}
      </div></div>}
      {showCompanyModal && selectedCompany && <CompanyModal company={selectedCompany} onClose={() => setShowCompanyModal(false)} onSaved={refreshCompany} />}
    </div>
  )
}

export default Companies