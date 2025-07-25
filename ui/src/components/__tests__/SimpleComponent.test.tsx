import { render, screen } from '@testing-library/react'

// Simple component for testing
const TestComponent = ({ title, value }: { title: string; value: string }) => (
  <div>
    <h3>{title}</h3>
    <p>{value}</p>
  </div>
)

describe('SimpleComponent', () => {
  it('renders component with props', () => {
    render(<TestComponent title="Test Title" value="Test Value" />)
    
    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test Value')).toBeInTheDocument()
  })

  it('renders different content', () => {
    render(<TestComponent title="Another Title" value="Another Value" />)
    
    expect(screen.getByText('Another Title')).toBeInTheDocument()
    expect(screen.getByText('Another Value')).toBeInTheDocument()
  })
})