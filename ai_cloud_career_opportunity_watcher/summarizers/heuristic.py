from __future__ import annotations

from summarizers.base import BaseSummarizer


class HeuristicSummarizer(BaseSummarizer):
    def summarize(self, opportunity) -> dict[str, str]:
        category_label = {"job": "채용", "news": "뉴스", "change": "변화 신호"}.get(
            opportunity.source_type,
            opportunity.source_type,
        )
        tech_text = ", ".join(opportunity.tech_stack[:4]) if opportunity.tech_stack else "핵심 기술 키워드 수동 확인 필요"
        location_text = opportunity.location or "위치 정보 없음"
        role_text = opportunity.role or "역할 정보 없음"

        summary_lines = [
            f"1) {opportunity.company_name}의 {category_label} 항목으로, 핵심 제목은 '{opportunity.title}'입니다.",
            f"2) 위치/역할 정보는 {location_text} / {role_text}이며 기술 키워드는 {tech_text}입니다.",
            f"3) 관련도 {opportunity.relevance_score:.0f}점, 시급성 {opportunity.urgency_score:.0f}점으로 우선 검토 가치가 있습니다.",
        ]
        why_it_matters = _why_it_matters(opportunity)
        recommended_action = _recommended_action(opportunity)
        return {
            "title": opportunity.title,
            "company": opportunity.company_name,
            "category": opportunity.source_type,
            "summary_text": "\n".join(summary_lines),
            "why_it_matters": why_it_matters,
            "recommended_action": recommended_action,
            "source_link": opportunity.url,
        }


def _why_it_matters(opportunity) -> str:
    if opportunity.source_type == "job":
        return "한국 내 AI/클라우드 역할 수요를 빠르게 파악하고 지원 우선순위를 정하는 데 직접 도움이 됩니다."
    if opportunity.source_type == "change":
        return "조직 변화나 투자/제품 신호는 채용 확대나 신규 포지션 오픈의 선행 지표가 될 가능성이 큽니다."
    return "해당 기업의 전략 변화와 채용 방향을 함께 읽을 수 있어 후속 모니터링 가치가 높습니다."


def _recommended_action(opportunity) -> str:
    if opportunity.source_type == "job":
        return "채용 공고를 저장하고 24시간 안에 JD와 경력 키워드 일치 여부를 체크하세요."
    if opportunity.source_type == "change":
        return "이 기업을 관심 목록에 추가하고 향후 7일간 채용 페이지 변화를 다시 확인하세요."
    return "뉴스 맥락을 기록하고 관련 채용 공고가 열리는지 다음 수집 주기에서 확인하세요."
