# EDA Analyzer

EDA Analyzer is a React and FastAPI application for exploring uploaded CSV and
Excel datasets.

## Requirements

- Node.js and npm
- Python 3.10 or newer

## Setup

From the project root, install frontend dependencies:

```powershell
npm install
```

Activate the backend environment and install backend dependencies:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

## Run locally

Run the backend and frontend in separate terminals from the project root.

```powershell
npm run backend:dev
```

The API listens on `http://127.0.0.1:8000`.

```powershell
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`, and upload a `.csv`,
`.xlsx`, or `.xls` file. After upload, choose a plot type and column, then
select `Generate graph`.

- Bar and pie charts count categorical values.
- Histograms, box plots, and distributions use one numeric column.
- Line and scatter plots use two numeric columns.
- Distribution charts include a density curve.

## Data assistant

The EDA Assistant answers questions from the currently uploaded dataset and
selected graph. It can explain charts, identify highest and lowest values,
describe trends, find outliers, and calculate averages, medians, ranges,
counts, missing values, and correlations. Upload a dataset and generate a
graph first for graph-specific answers.

## Uploaded dataset history

Uploaded datasets appear in Recent Analyses with their file name, row count,
column count, upload time, and status. Dataset metadata is stored in
`backend/data/datasets.sqlite3`, and chart data is stored in `backend/data`.
This is local development storage and is not intended for multi-user
production deployments.

## Checks

```powershell
npm run lint
npm run build
```
