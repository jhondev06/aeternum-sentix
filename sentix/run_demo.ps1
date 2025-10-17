# Demo setup script (Windows PowerShell)
Write-Host "Installing dependencies..."
python -m pip install -r sentix\requirements.txt

Write-Host "Generating demo data and training model..."
python sentix\init_model.py

Write-Host "Done. Demo data and model are ready."