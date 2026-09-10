import { useEffect, useRef, useState } from 'react'
import { dateToBelgian, isWeekend, parseBelgianToDate } from '../utils/date'

type Props = {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  id?: string
}

const WEEKDAY_LABELS = ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo']
const MONTH_LABELS = [
  'januari', 'februari', 'maart', 'april', 'mei', 'juni',
  'juli', 'augustus', 'september', 'oktober', 'november', 'december',
]

// Monday-first weekday index (0 = Monday .. 6 = Sunday)
const mondayFirstIndex = (date: Date) => (date.getDay() + 6) % 7

const buildMonthGrid = (year: number, month: number): (Date | null)[] => {
  const firstOfMonth = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const leadingBlanks = mondayFirstIndex(firstOfMonth)
  const cells: (Date | null)[] = Array(leadingBlanks).fill(null)
  for (let day = 1; day <= daysInMonth; day++) {
    cells.push(new Date(year, month, day))
  }
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

const isSameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()

// Reusable Belgian-format (dd/mm/yyyy) date input with a calendar popup.
const BelgianDateInput = ({ value, onChange, placeholder = 'dd/mm/jjjj', disabled, id }: Props) => {
  const [open, setOpen] = useState(false)
  const [viewDate, setViewDate] = useState(() => parseBelgianToDate(value) ?? new Date())
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const openCalendar = () => {
    if (disabled) return
    setViewDate(parseBelgianToDate(value) ?? new Date())
    setOpen(true)
  }

  const selectDay = (day: Date) => {
    onChange(dateToBelgian(day))
    setOpen(false)
  }

  const selected = parseBelgianToDate(value)
  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()
  const cells = buildMonthGrid(year, month)

  return (
    <div className="date-field" ref={containerRef}>
      <input
        id={id}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
      <button
        type="button"
        className="date-field__toggle"
        onClick={openCalendar}
        disabled={disabled}
        aria-label="Kies datum"
      >
        📅
      </button>
      {open && (
        <div className="date-field__calendar">
          <div className="date-field__calendar-header">
            <button type="button" onClick={() => setViewDate(new Date(year, month - 1, 1))} aria-label="Vorige maand">‹</button>
            <span>{MONTH_LABELS[month]} {year}</span>
            <button type="button" onClick={() => setViewDate(new Date(year, month + 1, 1))} aria-label="Volgende maand">›</button>
          </div>
          <div className="date-field__calendar-weekdays">
            {WEEKDAY_LABELS.map((label, index) => (
              <span key={label} className={index >= 5 ? 'date-field__weekend-label' : ''}>{label}</span>
            ))}
          </div>
          <div className="date-field__calendar-grid">
            {cells.map((day, index) => {
              if (!day) return <span key={index} />
              const weekend = isWeekend(day)
              const isSelected = selected ? isSameDay(day, selected) : false
              return (
                <button
                  type="button"
                  key={index}
                  onClick={() => selectDay(day)}
                  className={[
                    'date-field__day',
                    weekend ? 'date-field__day--weekend' : '',
                    isSelected ? 'date-field__day--selected' : '',
                  ].filter(Boolean).join(' ')}
                >
                  {day.getDate()}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default BelgianDateInput
