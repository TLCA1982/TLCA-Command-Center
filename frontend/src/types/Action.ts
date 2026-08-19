export interface Action {
  id?: string
  priority: string
  title: string
  customer: string
  contact: string
  source: string
  dueDate: string
  status: string
  group: string
  notes?: string
  actionType?: string
  webLink?: string
  microsoftList?: string
  lastModifiedDate?: string
}
