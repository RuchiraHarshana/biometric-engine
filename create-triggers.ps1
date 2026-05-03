$ErrorActionPreference = "Stop"
$token = (gcloud auth print-access-token)
$base = "https://cloudbuild.googleapis.com/v1/projects/biosecuregate/locations/us-central1/triggers"
$hdrs = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }

function Create-Trigger($name, $body) {
    try {
        $r = Invoke-WebRequest -Uri $base -Method POST -Headers $hdrs -Body ($body | ConvertTo-Json -Depth 10)
        Write-Host "OK: $name -> $(($r.Content | ConvertFrom-Json).id)"
    } catch {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        Write-Host "FAIL: $name -> $($reader.ReadToEnd())"
    }
}

# Staging CD
Create-Trigger "biometric-staging-cd" @{
    name = "biometric-staging-cd"
    filename = "cloudbuild.yaml"
    repositoryEventConfig = @{
        repository = "projects/biosecuregate/locations/us-central1/connections/biometric-conn/repositories/biometric-engine-repo"
        push = @{ branch = "^staging$" }
    }
    substitutions = @{
        _PROJECT_ID = "biosecuregate"
        _REGION = "us-central1"
        _REPOSITORY_NAME = "biometric-engine"
        _SERVICE_NAME = "biometric-engine"
        _MODEL_SERVICE_NAME = "biometric-model"
        _ENV = "staging"
        _ALLOW_UNAUTH = "true"
        _SUPABASE_URL_SECRET = "supabase-url-staging"
        _SUPABASE_SERVICE_KEY_SECRET = "supabase-service-key-staging"
        _JWT_SECRET_SECRET = "jwt-secret-staging"
    }
}

# Prod CD
Create-Trigger "biometric-prod-cd" @{
    name = "biometric-prod-cd"
    filename = "cloudbuild.yaml"
    repositoryEventConfig = @{
        repository = "projects/biosecuregate/locations/us-central1/connections/biometric-conn/repositories/biometric-engine-repo"
        push = @{ branch = "^main$" }
    }
    substitutions = @{
        _PROJECT_ID = "biosecuregate"
        _REGION = "us-central1"
        _REPOSITORY_NAME = "biometric-engine"
        _SERVICE_NAME = "biometric-engine"
        _MODEL_SERVICE_NAME = "biometric-model"
        _ENV = "prod"
        _ALLOW_UNAUTH = "false"
        _SUPABASE_URL_SECRET = "supabase-url-prod"
        _SUPABASE_SERVICE_KEY_SECRET = "supabase-service-key-prod"
        _JWT_SECRET_SECRET = "jwt-secret-prod"
    }
}

# PR CI
Create-Trigger "biometric-pr-ci" @{
    name = "biometric-pr-ci"
    filename = "cloudbuild.ci.yaml"
    repositoryEventConfig = @{
        repository = "projects/biosecuregate/locations/us-central1/connections/biometric-conn/repositories/biometric-engine-repo"
        pullRequest = @{ branch = ".*"; commentControl = "COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY" }
    }
}

# Verify
Write-Host "`nVerifying triggers..."
$list = Invoke-WebRequest -Uri $base -Headers $hdrs
($list.Content | ConvertFrom-Json).triggers | ForEach-Object { Write-Host "  - $($_.name)  [$($_.id)]" }
