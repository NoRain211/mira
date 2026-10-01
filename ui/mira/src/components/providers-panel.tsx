import { Loader2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import type { LlmAccountProvider, LlmAccounts } from "@/lib/api/settings"

const ROWS: { key: LlmAccountProvider; name: string; icon: string }[] = [
  {
    key: "chatgpt",
    name: "OpenAI (Codex login)",
    icon: "/provider-icons/openai.svg",
  },
  {
    key: "anthropic",
    name: "Anthropic (Claude)",
    icon: "/provider-icons/claude-color.svg",
  },
]

type Login = { loginId: string; url: string; code?: string; error?: string }

function errorText(e: unknown) {
  const msg = e instanceof Error ? e.message : String(e)
  const m = msg.match(/"detail":\s*"([^"]+)"/)
  return m ? m[1] : msg
}

export function ProvidersPanel({ onChanged }: { onChanged?: () => void }) {
  const [accounts, setAccounts] = useState<LlmAccounts | null>(null)
  const refresh = useCallback(() => {
    api.getLlmAccounts().then(setAccounts)
    onChanged?.()
  }, [onChanged])
  useEffect(() => {
    api.getLlmAccounts().then(setAccounts)
  }, [])
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

  const rows = ROWS.filter((r) =>
    r.name.toLowerCase().includes(search.trim().toLowerCase())
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Providers</CardTitle>
        <CardDescription>
          Sign in to ChatGPT/Codex or Claude. Their models then appear in every
          model picker alongside your API-key models.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input
          placeholder="Search providers..."
          aria-label="Search providers"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="space-y-2">
          {rows.map((row) => {
            const list = accounts?.accounts[row.key] ?? []
            const active = list.find((a) => a.active) ?? list[0]
            const login = logins[row.key]
            return (
              <div key={row.key} className="rounded-lg border bg-muted/30 p-3">
                <div className="flex items-center gap-3">
                  <img src={row.icon} alt="" aria-hidden className="h-5 w-5" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{row.name}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {active ? active.email || "Signed in" : "Not logged in"}
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

                {manage === row.key && list.length > 0 && (
                  <ul className="mt-3 space-y-1 border-t pt-3">
                    {list.map((a) => (
                      <li
                        key={a.id}
                        className="flex items-center gap-2 text-sm"
                      >
                        <span className="flex-1 truncate">
                          {a.email || a.id}
                          {a.active && (
                            <span className="ml-2 text-xs text-green-500">
                              In use
                            </span>
                          )}
                        </span>
                        {!a.active && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            onClick={() =>
                              act(() => api.activateLlmAccount(row.key, a.id))
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
                      <p className="text-xs text-destructive">{login.error}</p>
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
                            await api.completeClaudeLogin(login.loginId, pasted)
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
                          If that tab ends on an error page, copy its address
                          (or the code shown) and paste it here.
                        </p>
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
        </div>
      </CardContent>
    </Card>
  )
}
