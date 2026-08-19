import { CheckCircle2, ExternalLink, Key, Loader2, ShieldCheck, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { webClient } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuthStore } from '@/stores/authStore'

export default function BrokerSelect() {
  const { user } = useAuthStore()
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Direct Frontend API Key & Client ID entry state
  const [clientId, setClientId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [apiKeyMarket, setApiKeyMarket] = useState('')
  const [apiSecretMarket, setApiSecretMarket] = useState('')
  const [showMarketKeys, setShowMarketKeys] = useState(false)

  useEffect(() => {
    // Fetch current credentials to pre-fill client ID if existing
    const fetchBrokerConfig = async () => {
      try {
        const response = await webClient.get('/api/broker/credentials')
        if (response.data?.status === 'success' && response.data.data) {
          const creds = response.data.data
          if (creds.client_id) {
            setClientId(creds.client_id)
          }
        }
      } catch {
        // Ignore fallback
      } finally {
        setIsLoading(false)
      }
    }

    fetchBrokerConfig()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      if (!apiKey.trim() || !apiSecret.trim()) {
        setError('Please enter your AC Agarwal Interactive App Key and Secret Key.')
        setIsSubmitting(false)
        return
      }

      const payload = {
        broker_name: 'acagarwal',
        client_id: clientId.trim(),
        broker_api_key: apiKey.trim(),
        broker_api_secret: apiSecret.trim(),
        broker_api_key_market: (apiKeyMarket || apiKey).trim(),
        broker_api_secret_market: (apiSecretMarket || apiSecret).trim(),
      }

      const res = await webClient.post('/api/broker/direct-connect', payload)
      if (res.data?.status === 'success') {
        useAuthStore.setState((state) => ({
          user: state.user ? { ...state.user, broker: 'acagarwal' } : null,
        }))
        window.location.href = res.data.redirect || '/dashboard'
        return
      } else {
        throw new Error(res.data?.message || 'Authentication failed')
      }
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || 'Failed to authenticate with AC Agarwal Symphony XTS')
      setIsSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-8 px-4 bg-muted/20">
      <div className="container max-w-5xl">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          
          {/* Left side: Info & Features */}
          <div className="lg:col-span-5 space-y-6">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold mb-3">
                <Zap className="h-3.5 w-3.5" />
                <span>AlgoRivarV2 • AC Agarwal Dedicated</span>
              </div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">
                Connect Trading Account
              </h1>
              <p className="text-muted-foreground mt-2 text-sm">
                Welcome, <span className="font-semibold text-foreground">{user?.username}</span>! Connect your AC Agarwal Symphony XTS account to start automated algorithmic trading.
              </p>
            </div>

            <div className="space-y-3">
              <div className="flex items-start gap-3 p-3 rounded-lg border bg-card/60">
                <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-xs font-semibold">Symphony XTS Execution</h3>
                  <p className="text-xs text-muted-foreground">Ultra-low latency direct exchange order routing for NSE, BSE, NFO, and MCX.</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-lg border bg-card/60">
                <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-xs font-semibold">18 Options & Analysis Tools</h3>
                  <p className="text-xs text-muted-foreground">Live Option Chain, Straddle/Strangle charts, Vol Surface, GEX, and Arbitrage scanners.</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-lg border bg-card/60">
                <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-xs font-semibold">Strategy Engine & Scalping</h3>
                  <p className="text-xs text-muted-foreground">Visual Flow Builder, Python Strategy Host, and 1-click Scalping Terminal.</p>
                </div>
              </div>
            </div>

            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              <span>Credentials are encrypted & stored securely on your server.</span>
            </div>
          </div>

          {/* Right side: AC Agarwal Credentials Form */}
          <div className="lg:col-span-7">
            <Card className="shadow-2xl border-primary/20">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary font-bold text-sm">
                      AC
                    </div>
                    <div>
                      <CardTitle className="text-lg font-bold">AC Agarwal (Symphony XTS)</CardTitle>
                      <CardDescription className="text-xs">Enter your API credentials from the AC Agarwal portal</CardDescription>
                    </div>
                  </div>
                  <a
                    href="https://symphony.acagarwal.com:3000"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary flex items-center gap-1 hover:underline"
                  >
                    Portal <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </CardHeader>

              <CardContent>
                {error && (
                  <Alert variant="destructive" className="mb-4">
                    <AlertDescription className="text-xs">{error}</AlertDescription>
                  </Alert>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="clientId" className="text-xs font-semibold">
                      Client ID / UCC Code
                    </Label>
                    <Input
                      id="clientId"
                      placeholder="e.g. DM933 or your Account ID"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                      className="font-mono text-sm"
                      disabled={isSubmitting}
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="apiKey" className="text-xs font-semibold">
                      Interactive App Key (Trading)
                    </Label>
                    <Input
                      id="apiKey"
                      placeholder="Enter your Interactive App Key"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="font-mono text-sm"
                      disabled={isSubmitting}
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="apiSecret" className="text-xs font-semibold">
                        Interactive Secret Key
                      </Label>
                      <span className="text-[10px] text-muted-foreground">Symphony XTS password</span>
                    </div>
                    <Input
                      id="apiSecret"
                      type="password"
                      placeholder="Enter your Interactive Secret Key"
                      value={apiSecret}
                      onChange={(e) => setApiSecret(e.target.value)}
                      className="font-mono text-sm"
                      disabled={isSubmitting}
                      required
                    />
                  </div>

                  {/* Market Data Keys Collapsible */}
                  <div className="pt-2 border-t border-border">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-xs text-muted-foreground hover:text-foreground p-0 h-auto font-normal flex items-center gap-1.5"
                      onClick={() => setShowMarketKeys(!showMarketKeys)}
                    >
                      <Key className="h-3.5 w-3.5" />
                      <span>{showMarketKeys ? 'Hide Market Data Keys' : 'Configure Separate Market Data Keys (Optional)'}</span>
                    </Button>

                    {showMarketKeys && (
                      <div className="space-y-3 pt-3">
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">Market Data App Key</Label>
                          <Input
                            placeholder="Optional: Defaults to Interactive Key"
                            value={apiKeyMarket}
                            onChange={(e) => setApiKeyMarket(e.target.value)}
                            className="font-mono text-xs"
                            disabled={isSubmitting}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">Market Data Secret Key</Label>
                          <Input
                            type="password"
                            placeholder="Optional: Defaults to Interactive Secret"
                            value={apiSecretMarket}
                            onChange={(e) => setApiSecretMarket(e.target.value)}
                            className="font-mono text-xs"
                            disabled={isSubmitting}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  <Button
                    type="submit"
                    className="w-full font-semibold"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Connecting AC Agarwal...
                      </>
                    ) : (
                      'Connect AC Agarwal & Launch AlgoRivar'
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>

        </div>
      </div>
    </div>
  )
}
