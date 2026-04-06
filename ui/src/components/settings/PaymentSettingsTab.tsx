import { useEffect, useState } from 'react'
import { CreditCard, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { settingsApi } from '@/lib/api'

interface PaymentSettings {
  provider: string
  stripe_secret_key: string
  stripe_publishable_key: string
  stripe_webhook_secret: string
  checkout_success_url: string
  checkout_cancel_url: string
}

const DEFAULT_SETTINGS: PaymentSettings = {
  provider: 'stripe',
  stripe_secret_key: '',
  stripe_publishable_key: '',
  stripe_webhook_secret: '',
  checkout_success_url: '',
  checkout_cancel_url: '',
}

export function PaymentSettingsTab() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settings, setSettings] = useState<PaymentSettings>(DEFAULT_SETTINGS)

  useEffect(() => {
    settingsApi.getSetting('plugin_payment_settings')
      .then((response) => {
        setSettings({ ...DEFAULT_SETTINGS, ...(response.value || {}) })
      })
      .catch(() => {
        setSettings(DEFAULT_SETTINGS)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await settingsApi.updateSetting('plugin_payment_settings', settings)
      toast.success('Payment settings updated')
    } catch (error) {
      console.error('Failed to save payment settings:', error)
      toast.error('Failed to save payment settings')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border/40 bg-card p-6">
        <div className="mb-6 flex items-start gap-3">
          <div className="rounded-xl bg-primary/10 p-2 text-primary">
            <CreditCard className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Payment Settings</h2>
            <p className="text-sm text-muted-foreground">
              Configure tenant-wide Stripe credentials used by public plugin paywalls.
            </p>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="space-y-2">
            <Label htmlFor="payment-provider">Provider</Label>
            <Input
              id="payment-provider"
              value={settings.provider}
              onChange={(event) => setSettings((current) => ({ ...current, provider: event.target.value || 'stripe' }))}
              placeholder="stripe"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stripe-secret-key">Stripe secret key</Label>
            <Input
              id="stripe-secret-key"
              type="password"
              value={settings.stripe_secret_key}
              onChange={(event) => setSettings((current) => ({ ...current, stripe_secret_key: event.target.value }))}
              placeholder="sk_live_..."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stripe-publishable-key">Stripe publishable key</Label>
            <Input
              id="stripe-publishable-key"
              value={settings.stripe_publishable_key}
              onChange={(event) => setSettings((current) => ({ ...current, stripe_publishable_key: event.target.value }))}
              placeholder="pk_live_..."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stripe-webhook-secret">Stripe webhook secret</Label>
            <Input
              id="stripe-webhook-secret"
              type="password"
              value={settings.stripe_webhook_secret}
              onChange={(event) => setSettings((current) => ({ ...current, stripe_webhook_secret: event.target.value }))}
              placeholder="whsec_..."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="checkout-success-url">Checkout success URL</Label>
            <Input
              id="checkout-success-url"
              value={settings.checkout_success_url}
              onChange={(event) => setSettings((current) => ({ ...current, checkout_success_url: event.target.value }))}
              placeholder="https://app.example.com/p/socialhub?t=1&checkout=success"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="checkout-cancel-url">Checkout cancel URL</Label>
            <Input
              id="checkout-cancel-url"
              value={settings.checkout_cancel_url}
              onChange={(event) => setSettings((current) => ({ ...current, checkout_cancel_url: event.target.value }))}
              placeholder="https://app.example.com/p/socialhub?t=1&checkout=cancel"
            />
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Payment Settings
          </Button>
        </div>
      </div>
    </div>
  )
}
