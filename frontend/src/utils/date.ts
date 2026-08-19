// Safe date utilities: operate on ISO YYYY-MM-DD strings and Belgian display DD/MM/YYYY.

export const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/
export const BELGIAN_DATE_RE = /^\d{2}\/\d{2}\/\d{4}$/

export function isIsoDate(value: string | undefined): boolean {
  return !!value && ISO_DATE_RE.test(value)
}

export function isBelgianDate(value: string | undefined): boolean {
  return !!value && BELGIAN_DATE_RE.test(value)
}

// Convert DD/MM/YYYY -> YYYY-MM-DD (no Date parsing)
export function belgianToIso(value: string): string {
  if (!isBelgianDate(value)) return value
  const [dd, mm, yyyy] = value.split('/')
  return `${yyyy}-${mm}-${dd}`
}

// Convert YYYY-MM-DD -> DD/MM/YYYY
export function isoToBelgian(value: string | undefined): string {
  if (!value) return ''
  if (!isIsoDate(value)) {
    // attempt to extract first 10 chars if it's an ISO date-time
    if (value.length >= 10) {
      const maybe = value.slice(0, 10)
      if (ISO_DATE_RE.test(maybe)) {
        const [y, m, d] = maybe.split('-')
        return `${d}/${m}/${y}`
      }
    }
    return value
  }
  const [y, m, d] = value.split('-')
  return `${d}/${m}/${y}`
}

// Parse an ISO YYYY-MM-DD (or ISO datetime) into a Date at local midnight safely
export function parseIsoToDate(value: string | undefined): Date | null {
  if (!value) return null
  const iso = value.length >= 10 ? value.slice(0, 10) : value
  if (!ISO_DATE_RE.test(iso)) return null
  const [y, m, d] = iso.split('-').map((s) => parseInt(s, 10))
  // month in JS Date is 0-indexed
  return new Date(y, m - 1, d)
}

export function isValidBelgianDate(value: string): boolean {
  if (!isBelgianDate(value)) return false
  const [ddS, mmS, yyyyS] = value.split('/')
  const dd = parseInt(ddS, 10)
  const mm = parseInt(mmS, 10)
  const yyyy = parseInt(yyyyS, 10)
  if (yyyy < 1 || mm < 1 || mm > 12 || dd < 1) return false

  const daysInMonth = new Date(yyyy, mm, 0).getDate()
  return dd <= daysInMonth
}
