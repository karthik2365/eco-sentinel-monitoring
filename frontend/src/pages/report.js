import { navigate, store, authFetch } from '../main';
import { Navbar } from '../components/navbar';

export function renderReport(container) {
    const state = history.state || {};
    const analysisId = state.id || new URLSearchParams(window.location.search).get('id');

    if (!analysisId) {
        navigate('/dashboard');
        return;
    }

    container.innerHTML = '';
    container.appendChild(Navbar());

    const content = document.createElement('div');
    content.className = 'page-container';

    content.innerHTML = `
        <div class="page-content">
            <div class="page-header flex justify-between items-center">
                <div>
                    <h1 class="page-title">Analysis Report #${analysisId}</h1>
                    <p class="page-subtitle">AI-Generated Environmental Intelligence</p>
                </div>
                <div class="flex gap-1">
                    <button id="btn-download" class="action-btn primary">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        Download PDF
                    </button>
                    <button id="btn-back" class="action-btn secondary" onclick="history.back()">
                        Back to Analysis
                    </button>
                </div>
            </div>

            <div class="card" style="background: white; color: #1e293b; min-height: 500px;">
                <div id="report-content" style="padding: 20px;">
                    <div class="loader-container">
                        <div class="spinner"></div>
                        <div class="loader-text" style="color: #1e293b;">Loading report...</div>
                    </div>
                </div>
            </div>
        </div>
    `;

    container.appendChild(content);

    // Fetch report from API
    fetchReport(analysisId);

    async function fetchReport(id) {
        try {
            // Fetch analysis with report
            const res = await authFetch(`/api/analysis/${id}`);
            const data = await res.json();

            // Fetch report content
            const reportRes = await authFetch(`/api/analysis/reports/${id}`);

            const reportContent = document.getElementById('report-content');

            if (reportRes.ok) {
                const reportData = await reportRes.json();

                if (reportData.content_html) {
                    // Extract body content from full HTML
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(reportData.content_html, 'text/html');
                    const frame = document.createElement('iframe');
                    frame.title = 'Environmental assessment report';
                    frame.setAttribute('sandbox', '');
                    frame.style.cssText = 'width:100%;height:1100px;border:0;background:white';
                    frame.srcdoc = doc.documentElement.outerHTML;
                    reportContent.replaceChildren(frame);
                } else {
                    reportContent.innerHTML = createFallbackReport(data);
                }

                // Setup download button
                document.getElementById('btn-download').addEventListener('click', () => {
                    window.open(reportData.pdf_url, '_blank');
                });
            } else {
                reportContent.innerHTML = createFallbackReport(data);
            }

        } catch (err) {
            console.error('Error fetching report:', err);
            document.getElementById('report-content').innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <h3 style="color: #dc2626;">Error Loading Report</h3>
                    <p>Could not fetch report data. Please try again.</p>
                    <button class="action-btn primary" onclick="location.reload()">Retry</button>
                </div>
            `;
        }
    }

    function createFallbackReport(analysisData) {
        return `
            <div style="font-family: Arial, sans-serif;">
                <div style="background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%); color: white; padding: 30px; margin: -20px -20px 30px -20px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px; letter-spacing: 2px;">ECO-SENTINEL</h1>
                    <div style="margin-top: 10px; opacity: 0.9;">Environmental Intelligence Report</div>
                </div>
                
                <div style="background: #f1f5f9; padding: 15px; border-radius: 8px; margin-bottom: 25px;">
                    <p><strong>Report ID:</strong> ${analysisId} | <strong>Status:</strong> ${analysisData?.status || 'Unknown'}</p>
                </div>
                
                <h2 style="color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px;">Executive Summary</h2>
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 20px; border-radius: 8px; margin: 15px 0;">
                    <p>Analysis completed for the selected region. The AI-powered detection system has identified ${analysisData?.incidents?.length || 0} potential environmental incidents requiring attention.</p>
                </div>
                
                <h2 style="color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-top: 30px;">Recommendations</h2>
                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 20px; border-radius: 8px;">
                    <ol>
                        <li>Conduct on-ground verification of detected changes</li>
                        <li>Compare with historical satellite imagery for trend analysis</li>
                        <li>Notify relevant authorities if violations are confirmed</li>
                        <li>Schedule follow-up monitoring for the affected areas</li>
                    </ol>
                </div>
                
                <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
                    <p>Generated by Eco-Sentinel AI Environmental Monitoring System</p>
                </div>
            </div>
        `;
    }
}
