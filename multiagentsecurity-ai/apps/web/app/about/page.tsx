export default function AboutPage() {
  return (
    <div className="page-stack">
      <section className="hero-panel hero-panel-compact">
        <p className="eyebrow">About</p>
        <h1>Why this project exists</h1>
        <p className="lede">
          Multi-agent systems introduce new security questions around orchestration,
          trust boundaries, tool use, and collaborative failure modes.
        </p>
      </section>

      <section className="content-section">
        <div className="prose-block">
          <p>
            `multiagentsecurity.ai` is intended to become a practical hub for collecting
            research, organizing a shared taxonomy, and publishing structured intelligence
            about multi-agent security patterns.
          </p>
          <p>
            The current scaffold deliberately favors clean boundaries over surface area:
            a frontend that can evolve, an ingestion service that can be scheduled, and a
            schema that makes tagging and categorization explicit.
          </p>
          <p>
            TODO: replace this placeholder narrative with project-specific mission,
            governance, and editorial policy.
          </p>
        </div>
      </section>
    </div>
  );
}
