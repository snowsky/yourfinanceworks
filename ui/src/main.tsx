import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import './i18n' // Initialize i18n

// Set theme before React renders
const theme = localStorage.getItem('theme');
if (
  theme === 'dark' ||
  (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)
) {
  document.documentElement.classList.add('dark');
} else {
  document.documentElement.classList.remove('dark');
}

createRoot(document.getElementById("root")!).render(<App />);
