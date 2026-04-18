import { TagCard } from "@/components/taxonomy/TagCard";
import { getTaxonomyGroups } from "@/lib/queries/taxonomy";

export default function TaxonomyPage() {
  const groups = getTaxonomyGroups();

  return (
    <div className="page-stack">
      <section className="hero-panel hero-panel-compact">
        <p className="eyebrow">Taxonomy</p>
        <h1>Shared vocabulary for multi-agent security</h1>
        <p className="lede">
          Attack, architecture, and control tags will anchor both ingestion enrichment
          and user-facing discovery.
        </p>
      </section>

      <section className="content-section taxonomy-groups">
        {groups.map((group) => (
          <div key={group.key} className="taxonomy-group">
            <div className="section-heading">
              <h2>{group.title}</h2>
              <p>{group.description}</p>
            </div>
            <div className="card-grid card-grid-compact">
              {group.tags.map((tag) => (
                <TagCard key={tag.slug} tag={tag} />
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
