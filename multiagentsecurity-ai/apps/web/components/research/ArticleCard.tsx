import Link from "next/link";

import type { ResearchArticle } from "@/lib/queries/articles";

export function ArticleCard({ article }: { article: ResearchArticle }) {
  return (
    <article className="card">
      <div className="card-meta">
        <span>{article.publishedAt}</span>
        <span>{article.source}</span>
      </div>
      <h3>{article.title}</h3>
      <p>{article.summary}</p>
      <div className="pill-row">
        {article.tags.map((tag) => (
          <span key={tag} className="pill">
            {tag}
          </span>
        ))}
      </div>
      <Link className="text-link" href={`/article/${article.slug}`}>
        Read placeholder detail
      </Link>
    </article>
  );
}
