import Link from "next/link";
import { HealthStatusCard } from "@/components/shared/health-status-card";

const quickLinks = [
  { href: "/ontology", label: "Ontology Studio" },
  { href: "/explorer", label: "Object Explorer" },
  { href: "/risk-events", label: "Risk Events" },
  { href: "/mitigation-plans", label: "Mitigation Plans" },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-canvas text-ink">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-10 lg:px-10">
        <section className="grid gap-6 rounded-[2rem] border border-border bg-white/80 p-8 shadow-[0_25px_80px_rgba(71,44,25,0.08)] lg:grid-cols-[1.4fr_0.9fr]">
          <div className="space-y-5">
            <p className="font-display text-sm uppercase tracking-[0.35em] text-accent">
              Skeleton Phase
            </p>
            <div className="space-y-3">
              <h1 className="font-display text-4xl leading-tight sm:text-5xl">
                Ontology-first operations, with the runtime boundaries still intact.
              </h1>
              <p className="max-w-2xl text-lg text-stone-700">
                This initial monorepo phase wires a Next.js frontend to a FastAPI
                backend and leaves the ontology, governed actions, permissions, and
                deterministic operational workflows for later implementation tasks.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              {quickLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-full border border-ink px-4 py-2 text-sm font-semibold transition hover:bg-ink hover:text-white"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <HealthStatusCard />
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {[
            "Backend health integration",
            "App shell and placeholders",
            "Docker and local dev setup",
          ].map((item) => (
            <div
              key={item}
              className="rounded-[1.5rem] border border-border bg-white p-6 shadow-sm"
            >
              <p className="font-display text-xl">{item}</p>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
