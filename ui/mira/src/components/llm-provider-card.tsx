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
import type { LlmProviderStatus } from "@/lib/api/settings"

const PROVIDERS = [
  {
    value: "openai",
    label: "API key",
    hint: "OpenRouter or another endpoint from mira.yaml",
  },
  {
    value: "codex-cli",
    label: "ChatGPT subscription",
    hint: "Plus / Pro / Business via Codex",
  },
  {
    value: "claude-cli",
    label: "Claude subscription",
    hint: "Pro / Max via Claude Code",
  },
]

function errorText(e: unknown) {
  const msg = e instanceof Error ? e.message : String(e)
  const m = msg.match(/"detail":\s*"([^"]+)"/)
  return m ? m[1] : msg
}

export function LlmProviderCard({ onChanged }: { onChanged: () => void }) {
  const [status, setStatus] = useState<LlmProviderStatus | null>(null)
  const [busy, setBusy] = useState("")
  const [error, setError] = useState("")
  const [claudeToken, setClaudeToken] = useState("")

  const refresh = useCallback(() => api.getLlmProvider().then(setStatus), [])
  useEffect(() => {
    refresh()
  }, [refresh])

  // Poll while a ChatGPT device sign-in is waiting for approval.
  const pending = status?.codex.pending
  useEffect(() => {
    if (!pending) return
    const id = setInterval(refresh, 3000)
    return () => clearInterval(id)
  }, [pending, refresh])

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key)
    setError("")
    try {
      await fn()
      await refresh()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy("")
    }
  }

  if (!status) return null
  const connected: Record<string, boolean> = {
    openai: true,
    "codex-cli": status.codex.connected,
    "claude-cli": status.claude.connected,
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Model provider</CardTitle>
        <CardDescription>
          How Mira pays for reviews: an API key, or your ChatGPT / Claude
          subscription.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup">
          {PROVIDERS.map((p) => {
            const active = status.provider === p.value
            return (
              <button
                key={p.value}
                type="button"
                role="radio"
                aria-checked={active}
                disabled={!!busy}
                onClick={() =>
                  !active &&
                  run("provider", async () => {
                    await api.setLlmProvider(p.value)
                    onChanged()
                  })
                }
                className={`rounded-md border p-3 text-left text-sm transition-colors ${
                  active ? "border-primary bg-primary/10" : "hover:bg-muted/50"
                }`}
              >
                <div className="font-medium">{p.label}</div>
                <div className="text-xs text-muted-foreground">{p.hint}</div>
                {p.value !== "openai" && (
                  <div
                    className={`mt-1 text-xs ${
                      connected[p.value]
                        ? "text-green-500"
                        : "text-muted-foreground"
                    }`}
                  >
                    {connected[p.value] ? "Signed in" : "Not signed in"}
                  </div>
                )}
              </button>
            )
          })}
        </div>

        <div className="space-y-2 border-t pt-4">
          <h3 className="text-sm font-semibold">ChatGPT</h3>
          {status.codex.connected ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                Signed in with ChatGPT.
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!!busy}
                onClick={() => run("codex-out", api.codexLogout)}
              >
                Sign out
              </Button>
            </div>
          ) : pending ? (
            <div className="space-y-1 text-sm">
              <p>
                1. Open{" "}
                <a
                  href={pending.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  {pending.url}
                </a>{" "}
                and sign in.
              </p>
              <p>
                2. Enter code{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono">
                  {pending.code}
                </code>{" "}
                (expires in 15 minutes).
              </p>
              <p className="flex items-center text-xs text-muted-foreground">
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                Waiting for approval…
              </p>
            </div>
          ) : (
            <Button
              size="sm"
              disabled={!!busy}
              onClick={() => run("codex-in", api.startCodexLogin)}
            >
              {busy === "codex-in" && (
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              )}
              Sign in with ChatGPT
            </Button>
          )}
          {status.codex.error && !pending && !status.codex.connected && (
            <p className="text-xs whitespace-pre-wrap text-destructive">
              {status.codex.error}
            </p>
          )}
        </div>

        <div className="space-y-2 border-t pt-4">
          <h3 className="text-sm font-semibold">Claude</h3>
          {status.claude.connected ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                Claude subscription token saved.
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!!busy}
                onClick={() => run("claude-out", api.clearClaudeToken)}
              >
                Sign out
              </Button>
            </div>
          ) : (
            <form
              className="space-y-2"
              onSubmit={(e) => {
                e.preventDefault()
                run("claude-in", async () => {
                  await api.saveClaudeToken(claudeToken)
                  setClaudeToken("")
                })
              }}
            >
              <p className="text-xs text-muted-foreground">
                Run{" "}
                <code className="rounded bg-muted px-1 font-mono">
                  claude setup-token
                </code>{" "}
                on any machine, sign in with your Claude account, then paste the
                token here.
              </p>
              <div className="flex gap-2">
                <Input
                  type="password"
                  autoComplete="off"
                  aria-label="Claude OAuth token"
                  placeholder="sk-ant-oat01-…"
                  value={claudeToken}
                  onChange={(e) => setClaudeToken(e.target.value)}
                />
                <Button
                  size="sm"
                  type="submit"
                  disabled={!!busy || !claudeToken.trim()}
                >
                  Save
                </Button>
              </div>
            </form>
          )}
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
