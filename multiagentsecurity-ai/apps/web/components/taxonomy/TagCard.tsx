import type { TaxonomyTag } from "@/lib/queries/taxonomy";

export function TagCard({ tag }: { tag: TaxonomyTag }) {
  return (
    <article className="card card-compact">
      <p className="card-kicker">{tag.group}</p>
      <h3>{tag.label}</h3>
      <p>{tag.description}</p>
      <span className="text-link">{tag.slug}</span>
    </article>
  );
}
