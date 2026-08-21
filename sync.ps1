Write-Host "Saving and pushing changes..." -ForegroundColor Cyan
git add .
git commit -m "Update code for testing"
git push origin main
Write-Host " Code pushed! Now in GCP SSH run: git pull && sudo systemctl restart crm-test" -ForegroundColor Green
