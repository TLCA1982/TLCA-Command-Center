import type { Action } from '../types/Action'

type SummaryCard = {
  title: string
  value: string
  icon: string
  accent: string
  filter: string
}

export const sampleData = {
  summaryCards: [
    { title: 'Vandaag', value: '4', icon: '📅', accent: '#2563eb', filter: 'today' },
    { title: 'Wachtend', value: '3', icon: '⏳', accent: '#f59e0b', filter: 'waiting' },
    { title: 'Open offertes', value: '2', icon: '📄', accent: '#10b981', filter: 'offers' },
    { title: 'Opvolgen', value: '1', icon: '⚠️', accent: '#ef4444', filter: 'urgent' },
  ] as SummaryCard[],
  actions: [
    {
      priority: 'Hoog',
      title: 'Herziening subsidieaanvraag',
      customer: 'Mol CY',
      contact: 'Jos Heylen',
      source: 'E-mail',
      dueDate: '10 Jul',
      status: 'Open',
      group: 'today',
    },
    {
      priority: 'Gemiddeld',
      title: 'Offerte voor onderhoudscontract',
      customer: 'Fremach',
      contact: 'Liesbeth Peeters',
      source: 'Telefoon',
      dueDate: '12 Jul',
      status: 'Wacht op klant',
      group: 'waiting',
    },
    {
      priority: 'Laag',
      title: 'Documenten importeren',
      customer: 'CNH Industrial Belgium',
      contact: 'Kris De Smet',
      source: 'Portal',
      dueDate: '14 Jul',
      status: 'Wacht op leverancier',
      group: 'offers',
    },
    {
      priority: 'Hoog',
      title: 'Volgende stap klantcase',
      customer: 'Atelier DB',
      contact: 'Anke Vandenberg',
      source: 'Teams',
      dueDate: '15 Jul',
      status: 'Afgewerkt',
      group: 'urgent',
    },
  ] as Action[],
}
