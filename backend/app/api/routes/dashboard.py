from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AssociationStatus,
    Component,
    DashboardBucket,
    DashboardRiskComponent,
    DashboardSummary,
    Remediation,
    RemediationStatus,
    Severity,
    Vulnerability,
    VulnerabilityComponent,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def read_dashboard_summary(session: SessionDep, _current_user: CurrentUser) -> Any:
    vulnerabilities = session.exec(select(Vulnerability)).all()
    components = session.exec(select(Component)).all()
    associations = session.exec(
        select(VulnerabilityComponent).where(
            VulnerabilityComponent.status == AssociationStatus.CONFIRMED
        )
    ).all()
    remediations = session.exec(select(Remediation)).all()

    severity_counts = Counter(str(item.severity) for item in vulnerabilities)
    cvss_counts: Counter[str] = Counter()
    trend_counts: Counter[str] = Counter()
    vulnerability_map = {item.id: item for item in vulnerabilities}
    component_map = {item.id: item for item in components}
    for item in vulnerabilities:
        score = item.cvss_score_v4 or item.cvss_score_v3 or item.cvss_score_v2
        if score is None:
            cvss_counts["未知"] += 1
        elif Decimal(score) >= 9:
            cvss_counts["9–10"] += 1
        elif Decimal(score) >= 7:
            cvss_counts["7–8.9"] += 1
        elif Decimal(score) >= 4:
            cvss_counts["4–6.9"] += 1
        else:
            cvss_counts["0–3.9"] += 1
        if item.source_publish_date:
            trend_counts[item.source_publish_date.strftime("%Y-%m")] += 1

    risk_counts: dict[Any, Counter[str]] = defaultdict(Counter)
    for association in associations:
        vulnerability = vulnerability_map.get(association.vulnerability_id)
        if vulnerability:
            risk_counts[association.component_id][str(vulnerability.severity)] += 1
    top_components: list[DashboardRiskComponent] = []
    for component_id, counts in risk_counts.items():
        component = component_map.get(component_id)
        if component:
            top_components.append(
                DashboardRiskComponent(
                    component_id=component.id,
                    name=component.name,
                    purl=component.purl,
                    critical_count=counts[Severity.CRITICAL],
                    high_count=counts[Severity.HIGH],
                    total_count=sum(counts.values()),
                )
            )
    top_components.sort(
        key=lambda item: (item.critical_count, item.high_count, item.total_count),
        reverse=True,
    )
    remediation_counts = Counter(str(item.status) for item in remediations)
    pending = sum(
        1
        for item in remediations
        if item.status in {RemediationStatus.PENDING, RemediationStatus.IN_PROGRESS}
    )
    return DashboardSummary(
        vulnerability_count=len(vulnerabilities),
        component_count=len(components),
        association_count=len(associations),
        pending_risk_count=pending,
        severity_distribution=[
            DashboardBucket(label=level.value, count=severity_counts[level.value])
            for level in Severity
        ],
        cvss_distribution=[
            DashboardBucket(label=label, count=cvss_counts[label])
            for label in ("9–10", "7–8.9", "4–6.9", "0–3.9", "未知")
        ],
        publication_trend=[
            DashboardBucket(label=label, count=trend_counts[label])
            for label in sorted(trend_counts)[-12:]
        ],
        remediation_distribution=[
            DashboardBucket(label=status.value, count=remediation_counts[status.value])
            for status in RemediationStatus
        ],
        high_risk_components=top_components[:10],
    )
