"""
KTU Module Report Generator - WeasyPrint Implementation
Generates PDFs with color-coded priority tiers, question listings, and study order.
Optimized: parallel module generation, simplified CSS for faster rendering.
"""
import logging
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Dict, List
from collections import defaultdict

from django.conf import settings

from apps.subjects.models import Subject, Module
from apps.questions.models import Question
from apps.analytics.models import TopicCluster

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------
TIER_CONFIG = {
    1: {
        'bg': '#8B0000',
        'text_color': '#FFFFFF',
        'label': 'TOP PRIORITY - REPEATED 5 OR MORE TIMES',
        'legend': 'Tier 1 -- Repeated 5+ times',
    },
    2: {
        'bg': '#FF8C00',
        'text_color': '#FFFFFF',
        'label': 'HIGH PRIORITY - REPEATED 3 TO 4 TIMES',
        'legend': 'Tier 2 -- Repeated 3-4 times',
    },
    3: {
        'bg': '#FFD700',
        'text_color': '#222222',
        'label': 'MEDIUM PRIORITY - REPEATED 2 TIMES',
        'legend': 'Tier 3 -- Repeated 2 times',
    },
    4: {
        'bg': '#808080',
        'text_color': '#222222',
        'label': 'LOW PRIORITY - APPEARED ONCE',
        'legend': 'Tier 4 -- Appeared once',
    },
}


class KTUModuleReportGenerator:
    """Generates KTU-style module reports using WeasyPrint."""

    def __init__(self, subject: Subject):
        self.subject = subject

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_all_module_reports(self) -> Dict[int, Optional[str]]:
        """Generate reports for all 5 modules in parallel.

        Uses ThreadPoolExecutor with 5 workers (one per module) so all 5
        PDFs generate simultaneously instead of sequentially.

        Returns:
            dict mapping module_num -> pdf_path (or None on failure)
        """
        modules = list(Module.objects.filter(
            subject=self.subject, number__in=range(1, 6)
        ))

        if not modules:
            return {}

        results = {}

        with ThreadPoolExecutor(max_workers=min(5, len(modules))) as executor:
            future_to_module = {
                executor.submit(self._generate_module_if_changed, m): m
                for m in modules
            }
            for future in as_completed(future_to_module):
                module = future_to_module[future]
                try:
                    pdf_path = future.result()
                    results[module.number] = pdf_path
                except Exception as e:
                    logger.error(f"Parallel report gen failed for module {module.number}: {e}")
                    results[module.number] = None

        return results

    def _generate_module_if_changed(self, module: Module) -> Optional[str]:
        """Generate module report only if cluster data has changed.

        Computes a hash of the cluster data and compares with a stored hash.
        Skips regeneration if the data hasn't changed (cache hit).
        """
        clusters_by_tier = self._get_clusters_by_tier(module)

        # Compute hash of cluster data to check if report needs regeneration
        data_str = json.dumps(clusters_by_tier, sort_keys=True, default=str)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()

        output_dir = Path(settings.MEDIA_ROOT) / 'reports' / str(self.subject.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"Module_{module.number}.pdf"
        hash_path = output_dir / f"Module_{module.number}.hash"

        # Check if report already exists with same data hash
        if output_path.exists() and hash_path.exists():
            try:
                stored_hash = hash_path.read_text().strip()
                if stored_hash == data_hash:
                    logger.info(f"Report cache hit: Module {module.number} (data unchanged)")
                    return str(output_path)
            except Exception:
                pass

        # Generate the report
        pdf_path = self.generate_module_report(module)

        # Save the hash for future cache checks
        if pdf_path:
            try:
                hash_path.write_text(data_hash)
            except Exception:
                pass

        return pdf_path

    def generate_module_report(self, module: Module) -> Optional[str]:
        """Generate a single module PDF report.

        Returns:
            Absolute path to the generated PDF, or None on failure.
        """
        try:
            from xhtml2pdf import pisa

            output_dir = Path(settings.MEDIA_ROOT) / 'reports' / str(self.subject.id)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"Module_{module.number}.pdf"

            clusters_by_tier = self._get_clusters_by_tier(module)
            html_content = self._build_html(module, clusters_by_tier)

            with open(str(output_path), 'wb') as pdf_file:
                result = pisa.CreatePDF(html_content, dest=pdf_file)

            if result.err:
                logger.error(f"xhtml2pdf reported errors for module {module.number}: {result.err}")
                return None

            logger.info(f"Generated report: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to generate module {module.number} report: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _get_clusters_by_tier(self, module: Module) -> Dict[int, list]:
        """Return clusters grouped by priority_tier (1-4).

        Each entry contains the cluster itself and its related questions
        enriched with paper year/month information.
        """
        clusters = TopicCluster.objects.filter(
            subject=self.subject,
            module=module,
        ).order_by('priority_tier', '-frequency_count', 'topic_name')

        grouped: Dict[int, list] = defaultdict(list)
        for cluster in clusters:
            questions = (
                cluster.questions
                .select_related('paper')
                .order_by('paper__year', 'question_number')
            )
            q_list: List[dict] = []
            for q in questions:
                year = q.paper.year if q.paper else ''
                month = getattr(q.paper, 'detected_exam_month', '') or '' if q.paper else ''
                marks = q.marks or ''
                q_list.append({
                    'year': year,
                    'month': month,
                    'text': q.text,
                    'marks': marks,
                })
            grouped[cluster.priority_tier].append({
                'topic_name': cluster.topic_name,
                'frequency_count': cluster.frequency_count,
                'years_appeared': cluster.years_appeared or [],
                'questions': q_list,
            })
        return dict(grouped)

    # ------------------------------------------------------------------
    # HTML builder
    # ------------------------------------------------------------------
    def _build_html(self, module: Module, clusters_by_tier: Dict[int, list]) -> str:
        """Build the full HTML document string for the PDF."""

        subject_name = self.subject.name or ''
        subject_code = self.subject.code or ''
        module_number = module.number

        # --- CSS ---
        css = self._build_css()

        # --- Header ---
        header_html = (
            '<div class="header">'
            f'<h1>{subject_name}</h1>'
            f'<h2>{subject_code} &mdash; Module {module_number}</h2>'
            '<h3>Repeated Question Analysis</h3>'
            '</div>'
        )

        # --- Color Legend ---
        legend_html = '<div class="legend"><h4>Color Legend</h4><div class="legend-items">'
        for tier_num in (1, 2, 3, 4):
            cfg = TIER_CONFIG[tier_num]
            legend_html += (
                f'<span class="legend-item">'
                f'<span class="legend-swatch" style="background:{cfg["bg"]};"></span>'
                f'{cfg["legend"]}'
                f'</span>'
            )
        legend_html += '</div></div>'

        # --- Tier Sections ---
        tier_sections_html = ''
        for tier_num in (1, 2, 3, 4):
            cfg = TIER_CONFIG[tier_num]
            tier_clusters = clusters_by_tier.get(tier_num, [])

            tier_sections_html += (
                f'<div class="tier-heading" style="background:{cfg["bg"]}; color:{cfg["text_color"]};">'
                f'{cfg["label"]}'
                f'</div>'
            )

            if not tier_clusters:
                tier_sections_html += '<p class="no-data">No topics in this tier.</p>'
                continue

            for cluster_data in tier_clusters:
                tier_sections_html += (
                    f'<div class="cluster-block">'
                    f'<div class="topic-label">{cluster_data["topic_name"]}</div>'
                    f'<ul class="question-list">'
                )
                for q in cluster_data['questions']:
                    year_badge = self._format_year_badge(q['year'], q['month'])
                    marks_str = f'({q["marks"]} marks)' if q['marks'] else ''
                    tier_sections_html += (
                        f'<li>'
                        f'<span class="year-badge">{year_badge}</span> '
                        f'{q["text"]} '
                        f'<span class="marks">{marks_str}</span>'
                        f'</li>'
                    )
                tier_sections_html += '</ul></div>'

        # --- Priority Study Order ---
        study_order_html = (
            '<div class="study-order">'
            '<h3>Priority Study Order</h3>'
            '<ol>'
        )
        order_num = 1
        for tier_num in (1, 2, 3, 4):
            tier_clusters = clusters_by_tier.get(tier_num, [])
            for cluster_data in tier_clusters:
                study_order_html += f'<li>{cluster_data["topic_name"]}</li>'
                order_num += 1
        study_order_html += '</ol></div>'

        # --- Assemble full document ---
        html = (
            '<!DOCTYPE html>'
            '<html><head><meta charset="utf-8">'
            f'<style>{css}</style>'
            '</head><body>'
            f'{header_html}'
            f'{legend_html}'
            f'{tier_sections_html}'
            f'{study_order_html}'
            '</body></html>'
        )
        return html

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------
    @staticmethod
    def _build_css() -> str:
        return """
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: Arial, Helvetica, sans-serif;
                font-size: 11pt;
                color: #222;
                line-height: 1.5;
            }

            /* Header */
            .header {
                text-align: center;
                margin-bottom: 24px;
                border-bottom: 2px solid #333;
                padding-bottom: 12px;
            }
            .header h1 {
                font-size: 20pt;
                margin: 0 0 4px 0;
            }
            .header h2 {
                font-size: 14pt;
                margin: 0 0 4px 0;
                color: #444;
            }
            .header h3 {
                font-size: 12pt;
                margin: 0;
                color: #666;
                font-weight: normal;
            }

            /* Color legend */
            .legend {
                border: 1px solid #ccc;
                padding: 10px 14px;
                margin-bottom: 20px;
                background: #fafafa;
            }
            .legend h4 {
                margin: 0 0 8px 0;
                font-size: 11pt;
            }
            .legend-items {
                /* no flexbox -- xhtml2pdf uses ReportLab which doesn't support it */
            }
            .legend-item {
                display: inline;
                font-size: 9pt;
                margin-right: 16px;
            }
            .legend-swatch {
                display: inline-block;
                width: 12px;
                height: 12px;
                margin-right: 4px;
                border: 1px solid #999;
            }

            /* Tier headings */
            .tier-heading {
                padding: 10px 16px;
                font-size: 12pt;
                font-weight: bold;
                margin-top: 20px;
                margin-bottom: 8px;
                border-radius: 3px;
            }

            .no-data {
                font-style: italic;
                color: #888;
                margin-left: 16px;
            }

            /* Cluster blocks */
            .cluster-block {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 10px 14px;
                margin-bottom: 10px;
                background: #fff;
            }
            .topic-label {
                font-size: 13pt;
                font-weight: bold;
                margin-bottom: 6px;
            }
            .question-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .question-list li {
                padding: 4px 0;
                border-bottom: 1px solid #eee;
                font-size: 10pt;
            }
            .question-list li:last-child {
                border-bottom: none;
            }
            .year-badge {
                display: inline-block;
                background: #2c3e50;
                color: #fff;
                padding: 1px 7px;
                border-radius: 3px;
                font-size: 8.5pt;
                font-weight: bold;
                margin-right: 4px;
            }
            .marks {
                color: #888;
                font-size: 9pt;
            }

            /* Study Order */
            .study-order {
                margin-top: 28px;
                border: 2px solid #333;
                border-radius: 4px;
                padding: 14px 20px;
            }
            .study-order h3 {
                margin: 0 0 10px 0;
                font-size: 14pt;
                border-bottom: 1px solid #aaa;
                padding-bottom: 6px;
            }
            .study-order ol {
                margin: 0;
                padding-left: 22px;
            }
            .study-order ol li {
                padding: 3px 0;
                font-size: 10.5pt;
            }
        """

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_year_badge(year: str, month: str) -> str:
        """Return a compact [Year Month] string for the badge."""
        parts = []
        if year:
            parts.append(str(year))
        if month:
            parts.append(str(month))
        if parts:
            return '[' + ' '.join(parts) + ']'
        return '[N/A]'


def generate_ktu_module_reports(subject: Subject) -> Dict[int, Optional[str]]:
    """Convenience function: generate all module reports for a subject."""
    generator = KTUModuleReportGenerator(subject)
    return generator.generate_all_module_reports()
