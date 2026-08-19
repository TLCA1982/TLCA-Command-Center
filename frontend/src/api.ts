const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '')

const apiBaseUrl = configuredBaseUrl ?? `${window.location.protocol}//${window.location.hostname}:8000`

export const apiUrl = (path: string) => `${apiBaseUrl}/${path.replace(/^\/+/, '')}`
