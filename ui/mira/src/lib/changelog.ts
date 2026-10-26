export const latestRelease = {
  version: "0.10.0",
  date: "2026-10-26",
  sections: [
    {
      title: "Security",
      changes: [
        {
          title:
            "Breaking: comment commands require repository write access by default.",
          description:
            "GitHub, GitLab, and Forgejo now check permissions before running review, review-rest, help, pause, resume, reject, or free-form questions. Permission lookup failures deny access. To retain access for read-only users, add them to commands.allowed_users or a per-command commands.<name>.allowed_users list; commands.blocked_users always wins.",
        },
        {
          title: "Free-form disagreements respect the reject policy.",
          description:
            "A reply classified as disagreement resolves the thread and records rejected feedback only when its author can run reject; answering the reply also requires ask permission.",
        },
        {
          title: "Malformed outbound webhook URLs are contained.",
          description:
            "Invalid URLs are rejected during validation and cannot escape delivery error handling. HTTP redirects and other non-success delivery statuses are reported as failures.",
        },
      ],
    },
    {
      title: "Added",
      changes: [
        {
          title: "Broader source and configuration file support.",
          description:
            "Review and indexing recognize more languages, templates, build files, and configuration formats, while documentation remains excluded from indexing.",
        },
        {
          title: "Configurable indexing concurrency.",
          description:
            "index.llm_concurrency controls concurrent LLM summarization batches for full and incremental indexing. The default is 8, with a supported range of 1–32, so deployments can respect provider concurrency limits.",
        },
        {
          title: "In-app changelog.",
          description:
            "A Changelog page in the dashboard makes the latest release notes available alongside repository and review activity.",
        },
      ],
    },
    {
      title: "Fixed",
      changes: [
        {
          title: "Nested GitLab namespaces work throughout the dashboard.",
          description:
            "Repository details, setup, rules, learnings, and vulnerability routes accept nested groups, validate repository keys, and render useful breadcrumbs.",
        },
        {
          title: "GitHub Enterprise uses the configured API URL.",
          description:
            "Review and PR-description helpers now build clients against the deployment's configured GitHub endpoint.",
        },
        {
          title: "Indexing fetches files omitted from tarball caches.",
          description:
            "Conventions and package manifests fall back to individual source fetches when the cached archive does not contain them.",
        },
        {
          title: "Failed initial indexing updates repository status.",
          description:
            "Setup failures mark affected repositories as failed instead of leaving them pending indefinitely.",
        },
        {
          title: "PostgreSQL contributor quality matches SQLite.",
          description:
            "Per-author review and feedback quality is available when using the PostgreSQL index store.",
        },
        {
          title: "Walkthrough parsing accepts capitalized keys.",
          description:
            "Capitalized file and change-group keys from model output no longer cause valid walkthrough content to be lost.",
        },
        {
          title: "Self-critique handles missing verdict indexes.",
          description:
            "Positional matching is used only for a complete list of unindexed verdicts, preventing partial results from being assigned to the wrong findings.",
        },
        {
          title: "JSON output instructions survive provider routing.",
          description:
            "Chat Completions and Responses requests keep the required JSON instruction in user input, including when a proxy moves system content into separate instructions.",
        },
        {
          title: "DeepSeek respects disabled reasoning.",
          description:
            "Requests explicitly disable DeepSeek thinking when reasoning is set to off.",
        },
        {
          title: "Codex CLI loads review schemas correctly.",
          description:
            "Review schema imports use the shared tool-schema module.",
        },
        {
          title: "Dependency polling retains distinct npm resolutions.",
          description:
            "Multiple installed versions of the same package are preserved during vulnerability polling.",
        },
        {
          title: "Weekly review metrics use ISO week years.",
          description:
            "Reviews around New Year are grouped into the correct ISO week.",
        },
        {
          title: "React and React DOM stay aligned at 19.3.0.",
          description:
            "Matching runtime and type packages prevent the version mismatch that could leave the dashboard blank.",
        },
      ],
    },
    {
      title: "Changed",
      changes: [
        {
          title: "Clearer review diagnostics.",
          description:
            "GitHub webhook filter decisions are logged at INFO level, and LLM failures include transport timing or response-shape details without logging reasoning text.",
        },
        {
          title: "Dashboard dependencies refreshed.",
          description:
            "UI libraries and development tools have been updated, including Vite, ESLint, TypeScript tooling, and formatting utilities.",
        },
      ],
    },
  ],
}
