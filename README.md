# Eco-Sentinel

Satellite imagery comparison and AI-assisted environmental monitoring. Adapted from [Goofygiraffe06/agentathon](https://github.com/Goofygiraffe06/agentathon).

## Features
- Draw an area on a Leaflet map and preview RGB or NDVI satellite imagery.
- Compare a historical date with latest available imagery or another selected date.
- Inspect cloud-masked Sentinel-2 composites, approximate coverage and common-pixel NDVI change.
- Run AI-assisted change interpretation, generate PDF reports, and schedule monitoring while the local server is running.

## Run locally (macOS)
Requires Python 3.11 and Node.js 18+.

```sh
cp backend/.env.example backend/.env
# Configure OPENROUTER_API_KEY and GEE_PROJECT_ID in backend/.env.
# Set GEE_SERVICE_ACCOUNT to your own Earth Engine service-account JSON path.
./setup.command
./start.command
```

Open http://127.0.0.1:5050. Local demo login: `demo` / `demo123`. Stop the server with Ctrl+C.

Earth Engine requires an enabled, registered Google Cloud project and appropriate service-account access. Credentials, databases, reports and downloaded analysis images are deliberately excluded. Keep secrets local; never commit them. This repository starts with a clean history.

## Stack
Vanilla JavaScript, Vite, Leaflet/Leaflet Draw, Chart.js, Three.js/Globe.gl; Python/Flask, SQLAlchemy/SQLite, JWT, Socket.IO; Google Earth Engine and Sentinel-2/Cloud Score+; OpenRouter; xhtml2pdf/ReportLab.

## Verification
```sh
cd backend
../.venv/bin/python -m unittest discover -s tests -v
# Optional online Earth Engine mask regression:
PYTHONPATH=. ../.venv/bin/python tests/manual_check_pixel_masks.py
```
Tests use an isolated database, mocked AI and a repository sample image fixture. The original sample is retained only as a test fixture, not a current observation.

## Interpretation limits
Sentinel-2 RGB/NIR detail is 10 m per source pixel. Coverage and NDVI regional summaries are sampled at 120 m. Composites combine observations over a stated date window; they are not live photographs. Missing pixels are excluded from measurements. Low NDVI can indicate water or bare soil, not necessarily deforestation. AI findings and confidence scores require field verification. Free AI providers may time out or rate-limit; dated images remain available when AI fails.
