import { getApiToken, requireSignIn } from './auth'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '')

const apiBaseUrl = configuredBaseUrl ?? `${window.location.protocol}//${window.location.hostname}:8000`

export const apiUrl = (path: string) => `${apiBaseUrl}/${path.replace(/^\/+/, '')}`

export const apiFetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const address = input instanceof Request ? input.url : input.toString()
  if (new URL(address, window.location.href).origin !== new URL(apiBaseUrl).origin) {
    throw new Error('Dit verzoek behoort niet tot de Command Center API.')
  }
  const token = await getApiToken()
  const headers = new Headers(input instanceof Request ? input.headers : undefined)
  new Headers(init?.headers).forEach((value, name) => headers.set(name, value))
  headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(input, { ...init, headers, credentials: 'omit' })
  if (response.status === 401) requireSignIn()
  if (response.status === 403) throw new Error('Dit Microsoft-account heeft geen toegang tot het Command Center.')
  return response
}
