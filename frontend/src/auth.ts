import { PublicClientApplication, InteractionRequiredAuthError } from '@azure/msal-browser'

const clientId = 'f7bfbe0a-00bf-4669-900d-760245e770e5'
const tenantId = '5e06b648-4aab-43f8-9462-4ea4873be0a2'
const allowedObjectId = 'ad58799e-8d9f-47ff-a009-1fa0bb510d6d'
const scopes = [`api://${clientId}/access_as_user`]
const client = new PublicClientApplication({
  auth: { clientId, authority: `https://login.microsoftonline.com/${tenantId}`, redirectUri: `${window.location.origin}/`, postLogoutRedirectUri: `${window.location.origin}/` },
  cache: { cacheLocation: 'sessionStorage' },
})

// This check controls the screen; Azure independently validates API tokens and user access.
export const allowedAccount = () => client.getAllAccounts().find((account) =>
  account.idTokenClaims?.oid === allowedObjectId && account.tenantId === tenantId,
)
let initialization: Promise<void> | undefined
export const initializeAuth = () => {
  if (!initialization) initialization = (async () => {
    await client.initialize()
    await client.handleRedirectPromise()
    const account = allowedAccount()
    if (account) client.setActiveAccount(account)
  })().catch((error) => { initialization = undefined; throw error })
  return initialization
}
export const signIn = async () => {
  await initializeAuth()
  await client.loginRedirect({ scopes, loginHint: 'tomas@tlca.be', prompt: 'select_account' })
}
export const signOut = async () => {
  await initializeAuth()
  await client.logoutRedirect({ account: client.getActiveAccount() ?? undefined })
}
export const requireSignIn = () => window.dispatchEvent(new Event('tlca-auth-required'))
export const getApiToken = async () => {
  await initializeAuth()
  const account = allowedAccount()
  if (!account) {
    requireSignIn()
    throw new Error('Meld je aan met tomas@tlca.be om het Command Center te gebruiken.')
  }
  try {
    const result = await client.acquireTokenSilent({ scopes, account })
    return result.accessToken
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) requireSignIn()
    throw error
  }
}
