param([int]$Depth = 5)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$outDir = Join-Path $RepoRoot "out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if (Get-Command py -ErrorAction SilentlyContinue) {
  $python = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $python = "python"
} else {
  throw "Python was not found. Install Python or add it to PATH."
}

Write-Host "Starting Google Maps scraper..."
docker compose up -d | Out-Host

$day = (Get-Date).DayOfWeek.ToString()
switch ($day) {
  "Monday"    { $pack = "enix\keywords\casablanca-real-estate.txt"; $label = "real-estate" }
  "Tuesday"   { $pack = "enix\keywords\casablanca-hotels.txt"; $label = "hotels" }
  "Wednesday" { $pack = "enix\keywords\casablanca-events.txt"; $label = "events" }
  "Thursday"  { $pack = "enix\keywords\casablanca-dmc.txt"; $label = "dmc" }
  "Friday"    { $pack = "enix\keywords\casablanca-real-estate.txt"; $label = "real-estate-refresh" }
  "Saturday"  { $pack = "enix\keywords\casablanca-hotels.txt"; $label = "hotels-refresh" }
  "Sunday"    { $pack = "enix\keywords\casablanca-events.txt"; $label = "events-refresh" }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$raw = "out\casablanca-$label-$stamp-raw.csv"
$all = "out\casablanca-$label-$stamp-all.csv"
$qualified = "out\casablanca-$label-$stamp-qualified.csv"

Write-Host "Running Casablanca pack: $label"
& $python "scripts\scrape.py" --keywords-file $pack --city "Casablanca, Morocco" --depth $Depth --socials --out $raw
if ($LASTEXITCODE -ne 0) { throw "Scrape failed with exit code $LASTEXITCODE" }

& $python "enix\prepare_leads.py" $raw --out $all --qualified-out $qualified
if ($LASTEXITCODE -ne 0) { throw "Lead preparation failed with exit code $LASTEXITCODE" }

Copy-Item -Force $qualified "out\casablanca-qualified-latest.csv"
Copy-Item -Force $all "out\casablanca-all-latest.csv"

Write-Host "Done."
Write-Host "Qualified leads: $qualified"
Write-Host "Latest file: out\casablanca-qualified-latest.csv"
