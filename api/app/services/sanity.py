from __future__ import annotations

from dataclasses import dataclass

from app.models import ReviewedPaper


@dataclass(frozen=True)
class SanityCheckResult:
    status: str
    report: list[str]


class SanityCheckService:
    def audit(
        self,
        *,
        topic: str | None,
        query_used: str,
        total_candidates: int,
        papers: list[ReviewedPaper],
        requires_query_validation: bool,
        organization_mode: bool = False,
    ) -> SanityCheckResult:
        report: list[str] = []
        warnings = 0

        if requires_query_validation:
            query_message, query_ok = self._check_query(topic or "", query_used)
            report.append(query_message)
            warnings += 0 if query_ok else 1
        else:
            report.append("Query validation skipped because this workflow does not build an arXiv query.")

        candidate_message, candidate_ok = self._check_candidate_count(total_candidates, papers)
        report.append(candidate_message)
        warnings += 0 if candidate_ok else 1

        ordering_message, ordering_ok = self._check_fit_score_order(papers)
        report.append(ordering_message)
        warnings += 0 if ordering_ok else 1

        accepted_message, accepted_ok = self._check_acceptance_consistency(papers, organization_mode=organization_mode)
        report.append(accepted_message)
        warnings += 0 if accepted_ok else 1

        summary_message, summary_ok = self._check_summary_coverage(papers)
        report.append(summary_message)
        warnings += 0 if summary_ok else 1

        status = "passed" if warnings == 0 else "warning"
        report.insert(0, f"Sanity status: {status}. {warnings} warning(s) across query, review, and summary checks.")
        return SanityCheckResult(status=status, report=report)

    def _check_query(self, topic: str, query_used: str) -> tuple[str, bool]:
        normalized_query = query_used.strip().lower()
        topic_tokens = {token for token in topic.lower().split() if len(token) >= 4}
        token_hits = sorted(token for token in topic_tokens if token in normalized_query)

        if not normalized_query:
            return "Query check failed: the search agent did not produce a query string.", False
        if not topic_tokens:
            return "Query check passed: topic was too short for token validation, but a query string exists.", True
        if token_hits:
            return f"Query check passed: the arXiv query retains topic tokens {', '.join(token_hits[:5])}.", True
        return "Query check warning: the arXiv query does not visibly retain the main topic tokens.", False

    def _check_candidate_count(self, total_candidates: int, papers: list[ReviewedPaper]) -> tuple[str, bool]:
        if len(papers) > total_candidates:
            return (
                f"Candidate check failed: {len(papers)} reviewed papers exceeds {total_candidates} available candidates.",
                False,
            )
        return (
            f"Candidate check passed: {len(papers)} reviewed papers are consistent with {total_candidates} candidate(s).",
            True,
        )

    def _check_fit_score_order(self, papers: list[ReviewedPaper]) -> tuple[str, bool]:
        scores = [paper.fit_score for paper in papers]
        if scores == sorted(scores, reverse=True):
            return "Ordering check passed: papers are sorted by descending fit score.", True
        return "Ordering check warning: papers are not sorted by descending fit score.", False

    def _check_acceptance_consistency(
        self,
        papers: list[ReviewedPaper],
        *,
        organization_mode: bool,
    ) -> tuple[str, bool]:
        inconsistent = [paper.title for paper in papers if paper.is_fit and paper.fit_score < 0]
        if inconsistent:
            return f"Acceptance check failed: invalid negative fit scores for {', '.join(inconsistent[:3])}.", False

        if organization_mode:
            skipped = [paper.title for paper in papers if not paper.is_fit]
            if skipped:
                return "Acceptance check warning: organization mode should accept every uploaded paper.", False
            return "Acceptance check passed: organization mode accepted every uploaded paper.", True

        accepted = sum(paper.is_fit for paper in papers)
        rejected = len(papers) - accepted
        return f"Acceptance check passed: reviewer decisions produced {accepted} accepted and {rejected} rejected paper(s).", True

    def _check_summary_coverage(self, papers: list[ReviewedPaper]) -> tuple[str, bool]:
        missing = [paper.title for paper in papers if paper.is_fit and not paper.key_points_summary]
        leaked = [paper.title for paper in papers if not paper.is_fit and paper.key_points_summary]
        if missing or leaked:
            parts: list[str] = []
            if missing:
                parts.append(f"missing summaries for {', '.join(missing[:3])}")
            if leaked:
                parts.append(f"summaries attached to rejected papers {', '.join(leaked[:3])}")
            return f"Summary check warning: {'; '.join(parts)}.", False
        return "Summary check passed: accepted papers have summaries and rejected papers do not.", True
