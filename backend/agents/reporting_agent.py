"""
Reporting Agent

Responsible for generating professional, factual, and concise PDF reports.
"""

import logging
import os
import re
from html import escape
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from services.gemma_service import gemma_service  # Using standard AI service
from extensions import db
from models.analysis_incident import Report

logger = logging.getLogger(__name__)


class ReportingAgent(BaseAgent):
    """
    Agent for generating high-quality environmental reports.
    """
    
    SEVERITY_COLORS = {
        "critical": "#b91c1c",  # Darker red
        "high": "#c2410c",      # Darker orange
        "medium": "#a16207",    # Darker yellow/gold
        "low": "#15803d"        # Darker green
    }
    DEFAULT_SEVERITY_COLOR = "#4b5563"
    
    def __init__(self):
        super().__init__(agent_id="reporting_01", name="Intelligence Reporting Officer")

    def execute(
        self,
        analysis_id: int,
        incidents: List[Dict[str, Any]],
        report_title: str,
        image_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self.update_status("working")
        self.log_action(analysis_id, "start_reporting", reasoning="Drafting factual environmental report")
        
        try:
            # Generate content
            exec_summary = self._generate_executive_summary(report_title, incidents)
            detailed_analysis = self._generate_detailed_analysis(incidents)
            recommendations = self._generate_recommendations(incidents)

            # Build HTML content
            self.log_action(analysis_id, "formatting_html", reasoning="Compiling report layout")
            
            # Pass image paths directly - the PDF generator's link_callback will resolve them
            final_images = []
            if image_urls:
                for img_path in image_urls:
                    if img_path:
                        # Normalize path separators for HTML
                        normalized_path = "/static/images/analysis/" + os.path.basename(img_path)
                        final_images.append(normalized_path)
                    else:
                        final_images.append(None)
            
            html_content = self._build_html_report(
                analysis_id,
                report_title,
                exec_summary,
                detailed_analysis,
                recommendations,
                incidents,
                final_images
            )
            
            # Generate PDF
            self.log_action(analysis_id, "generating_pdf", reasoning="Rendering PDF document")
            from utils.pdf_generator import generate_pdf
            filename = f"local_report_{analysis_id}.pdf"
            pdf_url = generate_pdf(html_content, filename)
            
            if not pdf_url:
                raise Exception("Failed to generate PDF")
            
            # Save to database
            new_report = Report(
                analysis_id=analysis_id,
                title=report_title,
                content_html=html_content,
                pdf_url=pdf_url
            )
            db.session.add(new_report)
            db.session.commit()
            

            
            self.log_action(
                analysis_id,
                "report_complete",
                reasoning="Report generated and saved."
            )
            self.update_status("completed")
            
            return {
                "status": "success",
                "report_id": new_report.id,
                "pdf_url": pdf_url
            }

        except Exception as e:
            error_msg = f"Error in reporting: {str(e)}"
            logger.error(error_msg)
            
            self.log_action(
                analysis_id,
                "error",
                status="error",
                reasoning=error_msg
            )
            self.update_status("failed")
            
            return {
                "status": "error",
                "error": str(e)
            }

    def _generate_executive_summary(self, title: str, incidents: List[Dict[str, Any]]) -> str:
        incident_text = self._format_incident_data(incidents)
        
        prompt = f"""You are writing an Executive Summary for an environmental monitoring report. You HAVE the data below. Do NOT ask for more information.

REPORT TITLE: {title}
REPORT DATE: {datetime.now().strftime('%Y-%m-%d')}
TOTAL INCIDENTS DETECTED: {len(incidents)}

INCIDENT DATA (use this data directly):
{incident_text if incident_text else "No incidents detected."}

TASK: Write a 100-150 word executive summary covering:
- Number and types of incidents found
- Overall severity assessment
- Key locations affected

REQUIREMENTS: Professional tone. Plain text only. No markdown. No questions. Start writing immediately."""

        return self._clean_text(gemma_service.generate_text(prompt))

    def _generate_detailed_analysis(self, incidents: List[Dict[str, Any]]) -> str:
        if not incidents:
            return "No significant incidents detected during this analysis cycle."
        
        # Preserve the complete visual evidence rather than asking another model
        # to rewrite it or infer additional impacts.
        paragraphs = []
        for item in incidents:
            paragraphs.append(
                f"{item.get('category', 'Uncertain Change')} — "
                f"{item.get('severity', 'low')} severity (AI estimate). "
                f"{item.get('description', '')} "
                f"Confidence: {item.get('confidence', 0):.0%} (uncalibrated). "
                "Location refers to the selected area center. Field verification is required.")
        return self._clean_text('\n\n'.join(paragraphs))

    def _generate_recommendations(self, incidents: List[Dict[str, Any]]) -> str:
        if not incidents:
            return "1. Continue routine satellite monitoring.\n2. Maintain current surveillance schedule.\n3. No immediate action required."
        
        incident_text = self._format_incident_data(incidents)
        
        prompt = f"""You are an environmental compliance officer. You HAVE the incident data below. Do NOT ask for more information.

INCIDENTS REQUIRING RECOMMENDATIONS:
{incident_text}

TASK: Write exactly 4 specific, actionable recommendations. Each must be:
- Numbered (1. 2. 3. 4.)
- One sentence maximum
- Specific action (e.g., "Deploy ground inspection team to coordinates X")
- Recommend local records checks; do not invent regulations, penalties, or historical facts

REQUIREMENTS: Plain text only. No markdown. No questions. Start writing immediately with "1." """

        return self._clean_text(gemma_service.generate_text(prompt))

    def _format_incident_data(self, incidents: List[Dict[str, Any]]) -> str:
        if not incidents:
            return "None"
        
        formatted = []
        for i, inc in enumerate(incidents, 1):
            category = inc.get('category', 'Unknown')
            severity = inc.get('severity', 'medium')
            confidence = inc.get('confidence', 0.5)
            location = inc.get('location', {})
            description = inc.get('description', 'No description available')[:200]
            
            loc_str = f"Lat: {location.get('lat', 'N/A')}, Lon: {location.get('lon', 'N/A')}" if isinstance(location, dict) else str(location)
            
            formatted.append(f"""INCIDENT {i}:
  Category: {category}
  Severity: {severity.upper()}
  Confidence: {confidence:.0%}
  Location: {loc_str}
  Description: {description}
  Evidence limits: {inc.get('context', '')} {inc.get('history', '')}""")
        
        return "\n\n".join(formatted)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'[*#]', '', text)  # Remove MD styling
        return escape(text.strip())

    def _build_html_report(
        self, id: int, title: str, summary: str, analysis: str, 
        recs: str, incidents: List[Dict[str, Any]], images: Optional[List[str]]
    ) -> str:
        date_str = datetime.now().strftime('%d %B %Y')
        
        # Build image HTML (Table layout for PDF compatibility)
        images_html = ""
        if images and len(images) >= 2 and images[0] and images[1]:
            images_html = f"""
            <div class="section visuals">
                <h2>Visual Evidence</h2>
                <table style="border-collapse: collapse;">
                    <tr>
                        <td style="padding-right: 10px; vertical-align: top;">
                            <div class="img-label">BEFORE / SOURCE</div>
                            <img src="{images[0]}" width="230" style="border: 1px solid #ddd; border-radius: 4px;">
                        </td>
                        <td style="padding-left: 10px; vertical-align: top;">
                            <div class="img-label">AFTER / ANALYSIS</div>
                            <img src="{images[1]}" width="230" style="border: 1px solid #ddd; border-radius: 4px;">
                        </td>
                    </tr>
                </table>
            </div>
            """
        elif images and images[0]:
             images_html = f"""
            <div class="section visuals">
                <h2>Visual Evidence</h2>
                <div class="img-label">SATELLITE IMAGERY</div>
                <img src="{images[0]}" width="500" style="border: 1px solid #ddd; border-radius: 4px;">
            </div>
            """

        # Build Incident Table
        incident_rows = ""
        for idx, inc in enumerate(incidents, 1):
            severity = inc.get('severity', 'medium').lower()
            color = self.SEVERITY_COLORS.get(severity, self.DEFAULT_SEVERITY_COLOR)
            incident_rows += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px; color: {color}; font-weight: bold;">{severity.upper()}</td>
                <td style="padding: 10px;">{escape(inc.get('category', 'Unknown'))}</td>
                <td style="padding: 10px;">{escape(inc.get('description', 'N/A')[:100])}...</td>
            </tr>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{ size: A4; margin: 2.5cm; }}
        body {{ font-family: 'Helvetica', 'Arial', sans-serif; font-size: 10pt; line-height: 1.5; color: #333; }}
        h1 {{ font-size: 22pt; color: #111; margin-bottom: 5px; }}
        h2 {{ font-size: 14pt; color: #444; border-bottom: 2px solid #ddd; padding-bottom: 5px; margin-top: 25px; margin-bottom: 15px; }}
        .header {{ margin-bottom: 40px; border-bottom: 1px solid #eee; padding-bottom: 20px; }}
        .meta {{ color: #666; font-size: 9pt; }}
        .label {{ font-weight: bold; color: #222; }}
        .section {{ margin-bottom: 30px; }}
        .content-box {{ text-align: justify; }}
        .img-label {{ font-size: 8pt; font-weight: bold; color: #555; margin-bottom: 5px; text-transform: uppercase; }}
        table {{ text-align: left; }}
        th {{ background: #f9f9f9; padding: 10px; font-size: 9pt; }}
        .footer {{ position: fixed; bottom: 0; left: 0; right: 0; text-align: center; font-size: 8pt; color: #aaa; border-top: 1px solid #eee; padding-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ECO-SENTINEL <span style="color: #666; font-weight: normal;">Report</span></h1>
        <div class="meta">
            <div><span class="label">Analysis ID:</span> #{id}</div>
            <div><span class="label">Date:</span> {date_str}</div>
            <div><span class="label">Subject:</span> {title}</div>
        </div>
    </div>

    <div class="section">
        <h2>1. Executive Summary</h2>
        <div class="content-box">{summary}</div>
    </div>

    {images_html}

    <div class="section">
        <p>AI-assisted visual assessment, not a verified environmental violation. Confidence values are uncalibrated model estimates. Locations represent the selected area center; affected area is not measured. Seasonal variation and clouds may affect the comparison. No regulatory databases were queried.</p>
        <h2>3. Detailed Technical Analysis</h2>
        <div class="content-box">{analysis.replace(chr(10), '<br><br>')}</div>
    </div>

    <div class="section">
        <h2>4. Incident Log</h2>
        <table cellspacing="0">
            <thead>
                <tr>
                    <th width="15%">SEVERITY</th>
                    <th width="25%">TYPE</th>
                    <th width="60%">DESCRIPTION</th>
                </tr>
            </thead>
            <tbody>
                {incident_rows}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>5. Strategic Recommendations</h2>
        <div class="content-box">{recs.replace(chr(10), '<br>')}</div>
    </div>

    <div class="footer">
        Generated by Eco-Sentinel System | Confidential Document | {date_str}
    </div>
</body>
</html>
"""
