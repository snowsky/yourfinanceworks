
import type { Config } from "tailwindcss";

export default {
	darkMode: ["class"],
	content: [
		"./pages/**/*.{ts,tsx}",
		"./components/**/*.{ts,tsx}",
		"./app/**/*.{ts,tsx}",
		"./src/**/*.{ts,tsx}",
	],
	prefix: "",
	theme: {
		container: {
			center: true,
			padding: '2rem',
			screens: {
				'2xl': '1400px'
			}
		},
		extend: {
			fontFamily: {
				sans: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
				mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
				heading: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
				body: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
				display: ['DM Serif Display', 'Georgia', 'serif'],
			},
			fontWeight: {
				light: '300',
				normal: '400',
				medium: '500',
				semibold: '600',
				bold: '700',
				extrabold: '800',
			},
			fontSize: {
				// Enhanced typography scale
				'display-2xl': ['4.5rem', { lineHeight: '1', letterSpacing: '-0.02em' }],
				'display-xl': ['3.75rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
				'display-lg': ['3rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
				'display-md': ['2.25rem', { lineHeight: '1.2', letterSpacing: '-0.02em' }],
				'display-sm': ['1.875rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
				'heading-xl': ['1.5rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
				'heading-lg': ['1.25rem', { lineHeight: '1.4', letterSpacing: '-0.01em' }],
				'heading-md': ['1.125rem', { lineHeight: '1.5', letterSpacing: '0' }],
				'heading-sm': ['1rem', { lineHeight: '1.5', letterSpacing: '0' }],
				'body-xl': ['1.125rem', { lineHeight: '1.6', letterSpacing: '0' }],
				'body-lg': ['1rem', { lineHeight: '1.5', letterSpacing: '0' }],
				'body-md': ['0.875rem', { lineHeight: '1.4', letterSpacing: '0' }],
				'body-sm': ['0.75rem', { lineHeight: '1.3', letterSpacing: '0.05em' }],
				'caption': ['0.75rem', { lineHeight: '1.3', letterSpacing: '0.05em' }],
			},
			lineHeight: {
				'extra-tight': '1.1',
				'tight': '1.2',
				'snug': '1.3',
				'normal': '1.4',
				'relaxed': '1.5',
				'loose': '1.6',
			},
			letterSpacing: {
				'tighter': '-0.02em',
				'tight': '-0.01em',
				'normal': '0',
				'wide': '0.025em',
				'wider': '0.05em',
				'widest': '0.1em',
			},
			colors: {
				border: 'hsl(var(--border))',
				input: 'hsl(var(--input))',
				ring: 'hsl(var(--ring))',
				background: 'hsl(var(--background))',
				foreground: 'hsl(var(--foreground))',
				primary: {
					DEFAULT: 'hsl(var(--primary))',
					foreground: 'hsl(var(--primary-foreground))'
				},
				secondary: {
					DEFAULT: 'hsl(var(--secondary))',
					foreground: 'hsl(var(--secondary-foreground))'
				},
				destructive: {
					DEFAULT: 'hsl(var(--destructive))',
					foreground: 'hsl(var(--destructive-foreground))'
				},
				success: {
					DEFAULT: 'hsl(var(--success))',
					foreground: 'hsl(var(--success-foreground))'
				},
				warning: {
					DEFAULT: 'hsl(var(--warning))',
					foreground: 'hsl(var(--warning-foreground))'
				},
				muted: {
					DEFAULT: 'hsl(var(--muted))',
					foreground: 'hsl(var(--muted-foreground))'
				},
				accent: {
					DEFAULT: 'hsl(var(--accent))',
					foreground: 'hsl(var(--accent-foreground))'
				},
				popover: {
					DEFAULT: 'hsl(var(--popover))',
					foreground: 'hsl(var(--popover-foreground))'
				},
				card: {
					DEFAULT: 'hsl(var(--card))',
					foreground: 'hsl(var(--card-foreground))'
				},
				sidebar: {
					DEFAULT: 'hsl(var(--sidebar-background))',
					foreground: 'hsl(var(--sidebar-foreground))',
					primary: 'hsl(var(--sidebar-primary))',
					'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
					accent: 'hsl(var(--sidebar-accent))',
					'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
					border: 'hsl(var(--sidebar-border))',
					ring: 'hsl(var(--sidebar-ring))'
				},
				// Financial Status Colors
				financial: {
					navy: '#1e3a8a',
					forest: '#065f46',
					gold: '#f59e0b',
					emerald: '#10b981',
					rose: '#f43f5e',
				}
			},
			borderRadius: {
				lg: 'var(--radius)',
				md: 'calc(var(--radius) - 2px)',
				sm: 'calc(var(--radius) - 4px)'
			},
			keyframes: {
				'accordion-down': {
					from: {
						height: '0'
					},
					to: {
						height: 'var(--radix-accordion-content-height)'
					}
				},
				'accordion-up': {
					from: {
						height: 'var(--radix-accordion-content-height)'
					},
					to: {
						height: '0'
					}
				}
			},
			animation: {
				'accordion-down': 'accordion-down 0.2s ease-out',
				'accordion-up': 'accordion-up 0.2s ease-out'
			}
		}
	},
	plugins: [require("tailwindcss-animate")],
} satisfies Config;
