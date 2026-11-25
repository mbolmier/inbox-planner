"""Markdown report of an evaluation run (written to docs/evaluation.md)."""

from collections.abc import Sequence
from datetime import date

from inbox_planner.evaluation.labels import load_labels
from inbox_planner.evaluation.metrics import ACTIONABLE, ExtractionScores, instant, match_items
from inbox_planner.evaluation.runner import ExtractionRun, TriageRun, estimate_cost
from inbox_planner.llm.base import Usage
from inbox_planner.schemas import Category

CATEGORY_FR = {
    Category.APPOINTMENT: "rendez-vous",
    Category.DEADLINE: "échéance",
    Category.PROCEDURE: "démarche",
    Category.INFO: "info",
    Category.NOISE: "bruit",
}


def pct(value: float | None) -> str:
    return "–" if value is None else f"{value * 100:.0f} %"


def frac(part: int, whole: int) -> str:
    return f"{part}/{whole}" if whole else "–"


def usd(value: float | None) -> str:
    return "–" if value is None else f"{value:.3f} $".replace(".", ",")


def tokens(usage: Usage) -> str:
    return f"{usage.input_tokens:,} / {usage.output_tokens:,}".replace(",", " ")


def short(model: str) -> str:
    return model.removeprefix("claude-")


def render_report(
    triage_runs: Sequence[TriageRun],
    extraction_runs: Sequence[ExtractionRun],
    pipeline: tuple[TriageRun, ExtractionRun, ExtractionScores],
) -> str:
    labels = load_labels()
    expected_items = sum(len(label.items) for label in labels.values())
    lines = [
        "# Évaluation",
        "",
        f"*Générée par `inbox-planner eval` le {date.today():%d/%m/%Y}. "
        "Ne pas modifier à la main.*",
        "",
        f"- **Jeu de test :** {len(labels)} mails fictifs annotés à la main "
        f"([guide d'annotation](guide-annotation.md)), {expected_items} éléments attendus.",
        "- **Réponses des modèles :** enregistrées avec Claude Code "
        "(`claude -p`, abonnement Claude), puis rejouées depuis le cache : "
        "les chiffres sont reproductibles sans compte.",
        "- **Coût :** *estimé* au tarif public de l'API Anthropic, tous les tokens d'entrée "
        "au plein tarif (sans remise de cache). Aucun euro n'a été dépensé.",
        "- **Temps :** temps de réponse du modèle, moyenne par mail.",
        "",
        "## Tri",
        "",
        "« Utile » = tout sauf le bruit.",
        "",
        "| Modèle | Exactitude | Précision « utile » | Rappel « utile » | Échecs "
        "| Tokens entrée / sortie | Coût estimé (40 mails) | Temps / mail |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for run in triage_runs:
        s, st = run.scores, run.stats
        lines.append(
            f"| {short(st.model)} | {pct(s.accuracy)} | {pct(s.useful_precision)} "
            f"| {pct(s.useful_recall)} | {s.failures} | {tokens(st.usage)} | {usd(st.cost_usd)} "
            f"| {st.model_seconds / max(st.calls, 1):.1f} s |"
        )

    lines += [
        "",
        "## Extraction (sur les 40 mails)",
        "",
        "Un élément est **retrouvé** s'il a le bon type et exactement le bon instant, "
        "fuseau compris. Le rappel est donc l'exactitude des dates.",
        "",
        "| Modèle | Précision | Rappel (dates exactes) | Mauvais fuseau | Liens visio "
        "| ID + code | Récurrences | Durées | Coût estimé | Temps / mail |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for run in extraction_runs:
        s, st = run.scores, run.stats
        lines.append(
            f"| {short(st.model)} | {pct(s.precision)} | {pct(s.recall)} "
            f"({frac(s.matched, s.gold_items)}) | {s.wrong_zone} "
            f"| {frac(s.video_url_exact, s.video_expected)} "
            f"| {frac(s.meeting_details_exact, s.video_expected)} "
            f"| {frac(s.recurrence_exact, s.recurring_expected)} "
            f"| {frac(s.duration_exact, s.duration_expected)} | {usd(st.cost_usd)} "
            f"| {st.model_seconds / max(st.calls, 1):.1f} s |"
        )

    triage, extraction, end_to_end = pipeline
    lines += _pipeline_section(triage, extraction, end_to_end)
    lines += _errors_section(triage, extraction)
    return "\n".join(lines) + "\n"


def _pipeline_section(
    triage: TriageRun, extraction: ExtractionRun, scores: ExtractionScores
) -> list[str]:
    kept = [
        result
        for mid, result in extraction.results.items()
        if result is not None
        and (verdict := triage.results.get(mid)) is not None
        and verdict.category in ACTIONABLE
    ]
    extraction_usage = sum((r.usage for r in kept), Usage())
    extraction_cost = estimate_cost(extraction.stats.model, extraction_usage) or 0.0
    total = (triage.stats.cost_usd or 0.0) + extraction_cost
    return [
        "",
        f"## Chaîne retenue : tri {short(triage.stats.model)} → "
        f"extraction {short(extraction.stats.model)}",
        "",
        "L'extraction ne tourne que sur les mails que le tri juge utiles à planifier "
        "(rendez-vous, échéance, démarche).",
        "",
        f"- Précision : **{pct(scores.precision)}**, rappel : **{pct(scores.recall)}** "
        f"({frac(scores.matched, scores.gold_items)} éléments retrouvés).",
        f"- Mails envoyés à l'extraction : {len(kept)} sur 40.",
        f"- Coût estimé pour les 40 mails : **{usd(total)}** "
        f"(tri {usd(triage.stats.cost_usd)}, extraction {usd(extraction_cost)}).",
        "",
        "### Tri par catégorie",
        "",
        "| Catégorie | Précision | Rappel | Effectif |",
        "|---|---|---|---|",
        *(
            f"| {CATEGORY_FR[c]} | {pct(score.precision)} | {pct(score.recall)} | {score.support} |"
            for c, score in triage.scores.per_class.items()
        ),
    ]


def _errors_section(triage: TriageRun, extraction: ExtractionRun) -> list[str]:
    labels = load_labels()
    lines = ["", "## Erreurs à analyser", "", "### Tri", ""]
    triage_errors = [
        f"- `{mid}` : attendu *{CATEGORY_FR[label.category]}*, prédit "
        f"*{CATEGORY_FR[r.category] if (r := triage.results.get(mid)) else 'échec'}*"
        for mid, label in labels.items()
        if (r := triage.results.get(mid)) is None or r.category is not label.category
    ]
    lines += triage_errors or ["Aucune."]
    lines += ["", f"### Extraction ({short(extraction.stats.model)})", ""]
    extraction_errors = []
    for mid, label in labels.items():
        result = extraction.results.get(mid)
        found = result.items if result else ()
        matched = match_items(label.items, found)
        for item in label.items:
            if all(item is not g for g, _ in matched):
                extraction_errors.append(
                    f"- `{mid}` manqué : {item.title} ({instant(item).isoformat()})"
                )
        for item in found:
            if all(item is not p for _, p in matched):
                extraction_errors.append(
                    f"- `{mid}` en trop : {item.title} ({instant(item).isoformat()})"
                )
    lines += extraction_errors or ["Aucune."]
    return lines
