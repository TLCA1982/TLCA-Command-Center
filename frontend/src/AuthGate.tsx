import { useEffect, useState, type ReactNode } from 'react'
import { allowedAccount, getApiToken, initializeAuth, signIn, signOut } from './auth'

export default function AuthGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [checking, setChecking] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const expired = () => { setReady(false); setError('Je sessie is verlopen. Meld je opnieuw aan.') }
    window.addEventListener('tlca-auth-required', expired)
    initializeAuth().then(async () => {
      if (allowedAccount()) { await getApiToken(); if (active) setReady(true) }
    }).catch(() => { if (active) setError('Aanmelden kon niet worden afgerond. Probeer opnieuw met tomas@tlca.be.') })
      .finally(() => { if (active) setChecking(false) })
    return () => { active = false; window.removeEventListener('tlca-auth-required', expired) }
  }, [])
  const login = async () => {
    setBusy(true); setError('')
    try { await signIn() }
    catch { setError('Microsoft-aanmelding kon niet starten. Probeer opnieuw.'); setBusy(false) }
  }
  if (checking) return <main className="content"><p>Aanmelding controleren…</p></main>
  if (!ready) return <main className="content"><section className="table-card" style={{ maxWidth: 520, margin: '60px auto' }}>
    <h1>TLCA Command Center</h1>
    <p>Meld je aan met je Microsoft-account tomas@tlca.be.</p>
    {error && <p className="form-error" role="alert">{error}</p>}
    <button className="action-btn action-btn--primary" disabled={busy} onClick={login}>{busy ? 'Microsoft openen…' : 'Aanmelden met Microsoft'}</button>
  </section></main>
  return <><div style={{ display: 'flex', justifyContent: 'flex-end', padding: '8px 24px', gap: 16 }}><span>tomas@tlca.be</span><button onClick={() => { setReady(false); void signOut().catch(() => setError('Afmelden kon niet worden afgerond.')) }}>Afmelden</button></div>{children}</>
}
