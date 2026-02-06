# AkShare Quant Engine

FastAPI-based AkShare data service for n8n stock analysis workflow.

## API Endpoints

### GET /market
Get market context data (Shanghai Composite Index + Northbound funds)

### POST /stock
Stock deep analysis + position calculation

### GET /
Health check

## Deployment

This project is configured with GitHub Actions to automatically build and push Docker images to Docker Hub.

## Environment Variables

No special environment variables required.

## Usage with n8n

1. Deploy this service to ClawCloud or other container platform
2. Update n8n workflow HTTP nodes with your service URL:
   - Global Context (API): `https://your-url/market`
   - Stock Risk Analysis (API): `https://your-url/stock`
