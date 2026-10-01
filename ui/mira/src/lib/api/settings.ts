import { deleteJson, fetchJson, postJson, putJson } from "./http"

export type LlmProviderStatus = {
  provider: string
  codex: {
    connected: boolean
    pending: { url: string; code: string } | null
    error: string | null
  }
  claude: { connected: boolean }
}

// Model selection, cost estimate, and admin review-config overrides.
export const settingsApi = {
  getLlmProvider: () =>
    fetchJson<LlmProviderStatus>("/api/settings/llm-provider"),
  setLlmProvider: (provider: string) =>
    putJson<{ ok: boolean }>("/api/settings/llm-provider", { provider }),
  startCodexLogin: () =>
    postJson<{ url: string; code: string }>("/api/settings/codex-login", {}),
  codexLogout: () => deleteJson("/api/settings/codex-login"),
  saveClaudeToken: (token: string) =>
    putJson<{ ok: boolean }>("/api/settings/claude-token", { token }),
  clearClaudeToken: () => deleteJson("/api/settings/claude-token"),

  getModels: () =>
    fetchJson<{
      indexing_model: string
      review_model: string
      security_model: string
      backend: string
      indexing_source: "dashboard" | "config"
      review_source: "dashboard" | "config"
      security_source: "dashboard" | "config"
      config_indexing_model: string
      config_review_model: string
      config_security_model: string
      indexing_options: {
        value: string
        label: string
        recommended?: boolean
      }[]
      review_options: { value: string; label: string; recommended?: boolean }[]
      security_options: {
        value: string
        label: string
        recommended?: boolean
      }[]
      review_thinking_mode: string
      thinking_options: {
        value: string
        label: string
        recommended?: boolean
      }[]
      api_style: string
      api_style_options: {
        value: string
        label: string
        recommended?: boolean
      }[]
    }>("/api/settings/models"),

  saveModels: (
    indexing_model: string,
    review_model: string,
    security_model: string,
    review_thinking_mode: string = "off",
    api_style: string = "chat"
  ) =>
    putJson<{ ok: boolean }>("/api/settings/models", {
      indexing_model,
      review_model,
      security_model,
      review_thinking_mode,
      api_style,
    }),

  getCostEstimate: () =>
    fetchJson<{
      estimated_usd: number
      input_tokens: number
      output_tokens: number
      model: string
      file_count: number
    }>("/api/indexing/estimate"),

  getGlobalSettings: () =>
    fetchJson<{
      overrides: {
        filter?: Record<string, number | boolean | string>
        review?: Record<string, number | boolean | string>
      }
      effective: Record<string, unknown>
    }>("/api/admin/settings"),

  saveGlobalSettings: (
    overrides: Record<string, Record<string, number | boolean | string>>
  ) => putJson<{ ok: boolean }>("/api/admin/settings", { overrides }),
}
