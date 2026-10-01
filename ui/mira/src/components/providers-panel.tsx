import { Loader2 } from "lucide-react"
import { type FormEvent, useCallback, useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import type {
  ConnectedProvider,
  LlmAccountProvider,
  LlmAccounts,
  ProviderPreset,
  UsageWindow,
} from "@/lib/api/settings"

const ROWS: { key: LlmAccountProvider; name: string }[] = [
  { key: "chatgpt", name: "OpenAI (Codex login)" },
  { key: "anthropic", name: "Anthropic (Claude)" },
]

const ICONS: Record<string, string> = {
  chatgpt: "openai.svg",
  openai: "openai.svg",
  anthropic: "claude-color.svg",
  nvidia: "nvidia-color.svg",
  groq: "groq-color.svg",
  cerebras: "cerebras-color.svg",
  gemini: "gemini-color.svg",
  mistral: "mistral-color.svg",
  openrouter: "openrouter-color.svg",
  sambanova: "sambanova.svg",
  huggingface: "huggingface-color.svg",
  cloudflare: "workersai-color.svg",
  cohere: "cohere-color.svg",
  "ollama-cloud": "ollama-color.svg",
  ollama: "ollama-color.svg",
  xai: "grok.svg",
  deepseek: "deepseek-color.svg",
  moonshot: "moonshot-color.svg",
  zai: "zai.svg",
  together: "together.svg",
  fireworks: "fireworks-color.svg",
  deepinfra: "deepinfra-color.svg",
  novita: "novita.svg",
  hyperbolic: "hyperbolic-color.svg",
  nebius: "nebius.svg",
  baseten: "baseten.svg",
  "lm-studio": "lm-studio-color.svg",
  "llama-cpp": "llama-cpp.svg",
  vllm: "vllm-color.svg",
  litellm: "litellm.svg",
}

const TABS = [
  { value: "accounts", label: "Accounts" },
  { value: "free", label: "Free" },
  { value: "local", label: "Local" },
  { value: "paid", label: "Paid" },
] as const

// White tile so dark monochrome logos stay visible on the dark theme.
function ProviderIcon({ id, label }: { id: string; label: string }) {
  const file = ICONS[id]
  return file ? (
    <img
      src={`/provider-icons/${file}`}
      alt=""
      aria-hidden
      className="h-6 w-6 shrink-0 rounded bg-white p-0.5"
    />
  ) : (
    <span
      aria-hidden
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-muted text-xs font-semibold"
    >
      {label[0]?.toUpperCase()}
    </span>
  )
}

function ConnectForm({
  preset,
  onDone,
}: {
  preset?: ProviderPreset
  onDone: () => void
}) {
  const [label, setLabel] = useState("")
  const [baseUrl, setBaseUrl] = useState(preset?.base_url ?? "")
  const [key, setKey] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const keyMode = preset?.key ?? "optional"
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError("")
    try {
      await api.connectApiProvider({
        preset_id: preset?.id,
        label,
        base_url: baseUrl,
        api_key: key,
      })
      onDone()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={submit} className="mt-3 space-y-2 border-t pt-3">
      {!preset && (
        <Input
          aria-label="Provider name"
          placeholder="Name, e.g. My vLLM"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
      )}
      <Input
        aria-label="Base URL"
        placeholder="https://example.com/v1 (OpenAI-compatible)"
        value={baseUrl}
        onChange={(e) => setBaseUrl(e.target.value)}
      />
      {keyMode !== "none" && (
        <Input
          type="password"
          aria-label="API key"
          placeholder={
            keyMode === "required" ? "API key" : "API key (optional)"
          }
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center justify-between gap-2">
        {preset?.dashboard ? (
          <a
            href={preset.dashboard}
            target="_blank"
            rel="noreferrer"
            className="text-xs underline"
          >
            Get an API key
          </a>
        ) : (
          <span />
        )}
        <Button
          size="sm"
          type="submit"
          disabled={
            busy ||
            !baseUrl.trim() ||
            (!preset && !label.trim()) ||
            (keyMode === "required" && !key.trim())
          }
        >
          {busy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
          Connect
        </Button>
      </div>
    </form>
  )
}

function PresetRow({
  preset,
  connected,
  onChanged,
}: {
  preset: ProviderPreset
  connected: boolean
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="flex items-start gap-3">
        <ProviderIcon id={preset.id} label={preset.label} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
            {preset.label}
            {preset.tier === "free" && (
              <Badge variant="secondary" className="text-green-500">
                Free
              </Badge>
            )}
            <Badge variant="outline">
              {preset.key === "required"
                ? "API key"
                : preset.key === "optional"
                  ? "Key optional"
                  : "No key"}
            </Badge>
            {connected && (
              <Badge variant="secondary" className="text-green-500">
                Connected
              </Badge>
            )}
          </div>
          {preset.note && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {preset.note}
            </p>
          )}
        </div>
        {connected ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => api.disconnectApiProvider(preset.id).then(onChanged)}
          >
            Disconnect
          </Button>
        ) : (
          <Button
            size="sm"
            variant={open ? "outline" : "default"}
            onClick={() => setOpen(!open)}
          >
            {open ? "Cancel" : "Connect"}
          </Button>
        )}
      </div>
      {open && !connected && (
        <ConnectForm
          preset={preset}
          onDone={() => {
            setOpen(false)
            onChanged()
          }}
        />
      )}
    </div>
  )
}

type Login = { loginId: string; url: string; code?: string; error?: string }

type Usage = Partial<
  Record<LlmAccountProvider, Record<string, UsageWindow[] | undefined>>
>

// Claude redirects to localhost:54545, which only reaches Mira when both run on this machine.
const REMOTE = !["localhost", "127.0.0.1", "[::1]"].includes(
  window.location.hostname
)

function UsageBars({ windows }: { windows?: UsageWindow[] }) {
  if (!windows?.length) return null
  return (
    <div className="mt-2 space-y-1.5">
      {windows.map((w) => (
        <div key={w.label} className="flex items-center gap-2 text-xs">
          <span className="w-14 text-muted-foreground">{w.label}</span>
          <div
            className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label={`${w.label} usage`}
            aria-valuenow={Math.round(w.percent)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={`h-full ${w.percent >= 90 ? "bg-destructive" : "bg-primary"}`}
              style={{ width: `${Math.min(w.percent, 100)}%` }}
            />
          </div>
          <span className="w-10 text-right tabular-nums">
            {Math.round(w.percent)}%
          </span>
          {w.resets_at && (
            <span className="text-muted-foreground">
              resets{" "}
              {new Date(w.resets_at).toLocaleString(undefined, {
                weekday: "short",
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

function RateLimited() {
  return <span className="ml-2 text-xs text-destructive">Rate limited</span>
}

function errorText(e: unknown) {
  const msg = e instanceof Error ? e.message : String(e)
  const m = msg.match(/"detail":\s*"([^"]+)"/)
  return m ? m[1] : msg
}

export function ProvidersPanel({ onChanged }: { onChanged?: () => void }) {
  const [accounts, setAccounts] = useState<LlmAccounts | null>(null)
  const [apiProviders, setApiProviders] = useState<{
    presets: ProviderPreset[]
    connected: ConnectedProvider[]
  }>({ presets: [], connected: [] })
  const [tab, setTab] = useState<string>("accounts")
  const [customOpen, setCustomOpen] = useState(false)
  const [usage, setUsage] = useState<Usage>({})
  const loadUsage = useCallback(() => {
    api
      .getLlmUsage()
      .then((r) => setUsage(r.usage))
      .catch(() => setUsage({}))
  }, [])
  const refresh = useCallback(() => {
    api.getLlmAccounts().then(setAccounts)
    api.getApiProviders().then(setApiProviders)
    loadUsage()
    onChanged?.()
  }, [onChanged, loadUsage])
  useEffect(() => {
    api.getLlmAccounts().then(setAccounts)
    api.getApiProviders().then(setApiProviders)
    loadUsage()
  }, [loadUsage])
  const [search, setSearch] = useState("")
  const [manage, setManage] = useState<LlmAccountProvider | null>(null)
  const [logins, setLogins] = useState<
    Partial<Record<LlmAccountProvider, Login>>
  >({})
  const [pasted, setPasted] = useState("")
  const [busy, setBusy] = useState(false)

  const setLogin = (key: LlmAccountProvider, login?: Login) =>
    setLogins((prev) => ({ ...prev, [key]: login }))

  // Poll pending sign-ins until the server reports done/error.
  useEffect(() => {
    const pending = Object.entries(logins).filter(([, l]) => l && !l.error) as [
      LlmAccountProvider,
      Login,
    ][]
    if (!pending.length) return
    const id = setInterval(async () => {
      for (const [key, login] of pending) {
        const s = await api.getLlmLogin(login.loginId)
        if (s.status === "done") {
          setLogin(key, undefined)
          refresh()
        } else if (s.status === "error" || s.status === "unknown") {
          setLogin(key, { ...login, error: s.error || "Sign-in failed" })
        }
      }
    }, 2000)
    return () => clearInterval(id)
  }, [logins, refresh])

  const startLogin = async (key: LlmAccountProvider) => {
    // Open the tab synchronously so the browser doesn't block it as a popup.
    const tab =
      key === "anthropic" ? window.open("about:blank", "_blank") : null
    setBusy(true)
    try {
      const res = await api.startLlmLogin(key)
      setPasted("")
      setLogin(key, { loginId: res.login_id, url: res.url, code: res.code })
      if (tab) tab.location.href = res.url
    } catch (e) {
      tab?.close()
      setLogin(key, { loginId: "", url: "", error: errorText(e) })
    } finally {
      setBusy(false)
    }
  }

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      refresh()
    } finally {
      setBusy(false)
    }
  }

  const q = search.trim().toLowerCase()
  const rows = ROWS.filter((r) => r.name.toLowerCase().includes(q))
  const connectedIds = new Set(apiProviders.connected.map((c) => c.id))
  const connected = apiProviders.connected.filter((c) =>
    c.label.toLowerCase().includes(q)
  )
  const presets = apiProviders.presets.filter((p) =>
    p.label.toLowerCase().includes(q)
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Providers</CardTitle>
        <CardDescription>
          Sign in to ChatGPT/Codex or Claude, or connect API-key and local
          providers. Their models then appear in every model picker.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input
          placeholder="Search providers..."
          aria-label="Search providers"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList variant="line">
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="px-3">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="accounts" className="pt-2">
            <div className="space-y-2">
              {rows.map((row) => {
                const list = accounts?.accounts[row.key] ?? []
                const active = list.find((a) => a.active) ?? list[0]
                const login = logins[row.key]
                return (
                  <div
                    key={row.key}
                    className="rounded-lg border bg-muted/30 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <ProviderIcon id={row.key} label={row.name} />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">{row.name}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {active
                            ? active.email || "Signed in"
                            : "Not logged in"}
                          {active?.rate_limited && <RateLimited />}
                        </div>
                      </div>
                      {list.length ? (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setManage(manage === row.key ? null : row.key)
                            }
                          >
                            Manage
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => startLogin(row.key)}
                          >
                            Add account
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() =>
                              act(() => api.logOutLlmProvider(row.key))
                            }
                          >
                            Log out
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          disabled={busy}
                          onClick={() => startLogin(row.key)}
                        >
                          Log in
                        </Button>
                      )}
                    </div>
                    {active && (
                      <UsageBars windows={usage[row.key]?.[active.id]} />
                    )}

                    {manage === row.key && list.length > 0 && (
                      <ul className="mt-3 space-y-1 border-t pt-3">
                        {list.map((a) => (
                          <li
                            key={a.id}
                            className="flex flex-wrap items-center gap-2 text-sm"
                          >
                            <span className="flex-1 truncate">
                              {a.email || a.id}
                              {a.active && (
                                <span className="ml-2 text-xs text-green-500">
                                  In use
                                </span>
                              )}
                              {a.rate_limited && <RateLimited />}
                              <span className="ml-2 text-xs text-muted-foreground">
                                {(usage[row.key]?.[a.id] ?? [])
                                  .map(
                                    (w) =>
                                      `${w.label} ${Math.round(w.percent)}%`
                                  )
                                  .join(" · ")}
                              </span>
                            </span>
                            {!a.active && (
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={busy}
                                onClick={() =>
                                  act(() =>
                                    api.activateLlmAccount(row.key, a.id)
                                  )
                                }
                              >
                                Use
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy}
                              onClick={() =>
                                act(() => api.removeLlmAccount(row.key, a.id))
                              }
                            >
                              Remove
                            </Button>
                          </li>
                        ))}
                      </ul>
                    )}

                    {login && (
                      <div className="mt-3 space-y-2 border-t pt-3 text-sm">
                        {login.error ? (
                          <p className="text-xs text-destructive">
                            {login.error}
                          </p>
                        ) : row.key === "chatgpt" ? (
                          <>
                            <p>
                              Open{" "}
                              <a
                                href={login.url}
                                target="_blank"
                                rel="noreferrer"
                                className="underline"
                              >
                                {login.url}
                              </a>{" "}
                              and enter{" "}
                              <code className="rounded bg-muted px-1.5 py-0.5 font-mono">
                                {login.code}
                              </code>
                            </p>
                            <p className="flex items-center text-xs text-muted-foreground">
                              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                              Waiting for approval…
                            </p>
                          </>
                        ) : (
                          <form
                            className="space-y-2"
                            onSubmit={async (e) => {
                              e.preventDefault()
                              try {
                                await api.completeClaudeLogin(
                                  login.loginId,
                                  pasted
                                )
                                setLogin(row.key, undefined)
                                refresh()
                              } catch (err) {
                                setLogin(row.key, {
                                  ...login,
                                  error: errorText(err),
                                })
                              }
                            }}
                          >
                            {REMOTE ? (
                              <p className="text-xs text-muted-foreground">
                                Approve access on the Claude tab (
                                <a
                                  href={login.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="underline"
                                >
                                  reopen
                                </a>
                                ). It then lands on a localhost page that won't
                                load. Copy that page's address and paste it
                                here.
                              </p>
                            ) : (
                              <>
                                <p className="flex items-center text-xs text-muted-foreground">
                                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                                  Finish signing in on the Claude tab (
                                  <a
                                    href={login.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="mx-1 underline"
                                  >
                                    reopen
                                  </a>
                                  ).
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  If that tab ends on an error page, copy its
                                  address (or the code shown) and paste it here.
                                </p>
                              </>
                            )}
                            <div className="flex gap-2">
                              <Input
                                aria-label="Claude redirect URL or code"
                                placeholder="http://localhost:54545/callback?code=…"
                                value={pasted}
                                onChange={(e) => setPasted(e.target.value)}
                              />
                              <Button
                                size="sm"
                                type="submit"
                                disabled={!pasted.trim()}
                              >
                                Submit
                              </Button>
                            </div>
                          </form>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
              {connected.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3"
                >
                  <ProviderIcon id={c.id} label={c.label} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{c.label}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {c.base_url}
                      {c.has_key ? " · API key" : ""}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      api.disconnectApiProvider(c.id).then(refresh)
                    }
                  >
                    Disconnect
                  </Button>
                </div>
              ))}
            </div>
          </TabsContent>
          {(["free", "local", "paid"] as const).map((tier) => (
            <TabsContent key={tier} value={tier} className="space-y-2 pt-2">
              {presets
                .filter((p) => p.tier === tier)
                .map((p) => (
                  <PresetRow
                    key={p.id}
                    preset={p}
                    connected={connectedIds.has(p.id)}
                    onChanged={refresh}
                  />
                ))}
            </TabsContent>
          ))}
        </Tabs>
        {customOpen ? (
          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="flex items-center justify-between text-sm font-medium">
              Custom OpenAI-compatible provider
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setCustomOpen(false)}
              >
                Cancel
              </Button>
            </div>
            <ConnectForm
              onDone={() => {
                setCustomOpen(false)
                setTab("accounts")
                refresh()
              }}
            />
          </div>
        ) : (
          <div className="text-right">
            <button
              type="button"
              className="text-xs underline"
              onClick={() => setCustomOpen(true)}
            >
              Provider not listed? Add a custom one
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
