import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { latestRelease } from "@/lib/changelog"
import { useDocumentTitle } from "@/lib/hooks"

export function ChangelogPage() {
  useDocumentTitle("Changelog")

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Changelog</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          What’s new in Mira. Read the{" "}
          <a
            href="https://docs.miracode.ai/changelog"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4"
          >
            full release history
          </a>
          .
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mira {latestRelease.version}</CardTitle>
          <CardDescription>
            <time dateTime={latestRelease.date}>26 October 2026</time>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {latestRelease.sections.map((section) => (
            <section key={section.title}>
              <h2 className="mb-3 text-base font-semibold">{section.title}</h2>
              <ul className="list-disc space-y-3 pl-5 text-sm leading-relaxed">
                {section.changes.map((change) => (
                  <li key={change.title}>
                    <strong className="font-medium">{change.title}</strong>{" "}
                    <span className="text-muted-foreground">
                      {change.description}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
