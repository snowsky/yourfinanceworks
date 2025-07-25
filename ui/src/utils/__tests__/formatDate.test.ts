import { formatDate } from '../formatDate'

describe('formatDate', () => {
  it('formats date correctly', () => {
    const date = new Date('2024-01-15T10:30:00Z')
    const formatted = formatDate(date)
    expect(formatted).toMatch(/Jan 15, 2024/)
  })

  it('handles string dates', () => {
    const dateString = '2024-01-15'
    const formatted = formatDate(dateString)
    expect(formatted).toMatch(/Jan 15, 2024/)
  })
})