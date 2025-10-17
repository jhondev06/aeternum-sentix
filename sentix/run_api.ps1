# Run FastAPI server (Windows PowerShell)
Write-Host "Starting Sentix API..."
python -m uvicorn sentix.api.app:app --host 0.0.0.0 --port 8000