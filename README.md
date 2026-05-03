(**Project**

BioSecureGate — Biometric backend (FastAPI) with Supabase storage, ONNX model integration, JWT/TOTP + Email OTP 2FA.

**Quick Start**

- Clone repo and create a Python virtual environment.

	```bash
	python -m venv .venv
	.venv\Scripts\Activate.ps1   # PowerShell on Windows
	pip install --upgrade pip
	pip install -r requirements.txt
	```

- Configure environment: copy `.env.example` to `.env` (or edit `.env`) and set the following at minimum:

- **Required**:
	- `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` — your Supabase project
	- `ADMIN_EMAIL` and `ADMIN_EMAIL_PASSWORD` — bootstrap admin credentials

- **SMTP (email OTP)** — for production use a provider (Gmail requires an App Password):
	- `SMTP_HOST` (e.g. smtp.gmail.com)
	- `SMTP_PORT` (e.g. 587)
	- `SMTP_USER` (sender email)
	- `SMTP_PASS` (App Password — single 16-character string, no spaces)
	- `SMTP_FROM` (sender email)

- Start the FastAPI app (do NOT use `--reload` in production; use it only during development when comfortable with reloader behavior on Windows):

	```bash
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
	```

**Seeding admin user**

- To add an admin user (runs against Supabase):

	```bash
	python -m scripts.seed_admin --email admin@example.com --password TempPass1!
	```

**SMTP testing**

- Test email sending locally:

	```bash
	python -m scripts.test_smtp
	```

**Model service**

- The ONNX model service runs separately and provides embedding/template endpoints on port `8001` by default. Start it during development with:

	```powershell
	(.venv) PS G:\Ai_biometric\biometric-engine> uvicorn model_service.main:app --host 0.0.0.0 --port 8001 --reload
	```

- Ensure `MODEL_SERVICE_URL` in `.env` matches the service address (e.g. `http://127.0.0.1:8001`). Place `arcface.onnx` under `app/models/` or update `FACE_MODEL_PATH` accordingly.
- In production run the model service without `--reload` and behind a process manager.

**Scanner agent (optional)**

- The repository includes a `scanner_agent` utility that can be run separately. It's useful to run it in its own virtual environment to isolate dependencies.

- Create and activate a scanner venv (PowerShell):

	```powershell
	python -m venv scanner-venv
	.\scanner-venv\Scripts\Activate.ps1
	pip install --upgrade pip
	pip install -r requirements.txt   # or requirements.scanner.txt if present
	```

- Run the scanner agent from the project root:

	```powershell
	(.venv) PS G:\Ai_biometric\biometric-engine> python -m scanner_agent
	```

	Or, if you prefer the scanner venv:

	```powershell
	(& .\scanner-venv\Scripts\Activate.ps1) ; python -m scanner_agent
	```

- The scanner agent may have additional config; check `scanner_agent/README.py` or `scanner-agent.spec` in the repo for details.

**API endpoints (important)**

- Login (step 1): `POST /api/auth/login` — returns a `temp_token` for 2FA.
- Email OTP send (manual): `POST /api/auth/otp/send` — returns `otp_token` (dev only).
- 2FA verify: `POST /api/auth/2fa/verify` — exchange temp token + code for access token.
- Persons list (admin): `GET /api/persons` — list persons and metadata.
- Person partial update (admin/officer): `PATCH /api/persons/{person_id}` — update fields; only admins may modify `criminal_records`.

	- Request example (frontend):

		```js
		// include Authorization: Bearer <access_token>
		fetch(`http://127.0.0.1:8000/api/persons/${personId}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
			body: JSON.stringify({ full_name: 'New Name', criminal_records: '...' })
		})
		```

**Frontend integration (notes)**

- The backend enforces permissions. Update your frontend dashboard to:
	- Add an Edit button that opens a form prefilled with person data.
	- Only enable `criminal_records` input for users with role `admin`.
	- Call the `PATCH /api.persons/{id}` endpoint with the user's access token.

**Database / Supabase**

- Create a `person_audits` table (recommended) to store audit logs with fields: `id`, `person_id`, `changed_by`, `changed_at` (timestamptz), `changes` (json/text).

**Development tips**

- If you modify server code frequently on Windows, run without the reloader if you encounter `WatchFiles` / multiprocessing issues:
	```bash
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
	```

- Always keep `SMTP_PASS` secure and never commit `.env` to git.

**Testing & debugging**

- Use `scripts/smoke_test.py` to exercise common flows (enroll, match, auth). Adjust scripts as needed for your environment.

**Contributing**

- Follow the existing project structure. Run tests and manual flows for changes to auth, storage, or model integration.

**Contact / Support**

- For issues, open a GitHub issue on the repository.

---

## Google Cloud Run Deployment

This project deploys two Cloud Run services:
- **`SERVICE_NAME`** — the main FastAPI backend (`app.main:app`, port 8080)
- **`MODEL_SERVICE_NAME`** — the ONNX model service (`model_service.main:app`, port 8080)

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated
- Docker installed locally (for local testing)
- A GCP project with billing enabled

---

### Step 1 — Authenticate and set your project

```bash
gcloud auth login
gcloud config set project PROJECT_ID
```

---

### Step 2 — Enable required GCP APIs

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

---

### Step 3 — Create Artifact Registry Docker repository

```bash
gcloud artifacts repositories create REPOSITORY_NAME \
  --repository-format=docker \
  --location=REGION \
  --project=PROJECT_ID
```

---

### Step 4 — (Optional) Test Docker build locally

```bash
# Build backend
docker build -t local-backend .

# Build model service
docker build -t local-model -f Dockerfile.model .

# Run backend locally (needs a .env file)
docker run --env-file .env -p 8080:8080 local-backend

# Run model service locally
docker run --env-file .env -p 8081:8080 local-model
```

Visit `http://localhost:8080/docs` to verify the backend API is working.

---

### Step 5 — Submit Cloud Build (builds + pushes + deploys both services)

```bash
gcloud builds submit . \
  --config=cloudbuild.yaml \
  --substitutions=\
_PROJECT_ID=PROJECT_ID,\
_REGION=REGION,\
_REPOSITORY_NAME=REPOSITORY_NAME,\
_SERVICE_NAME=SERVICE_NAME,\
_MODEL_SERVICE_NAME=MODEL_SERVICE_NAME
```

---

### Step 6 — Wire model service URL into the backend

After first deployment, get the model service URL:

```bash
gcloud run services describe MODEL_SERVICE_NAME \
  --region=REGION \
  --format='value(status.url)'
```

Then update the backend Cloud Run service with that URL:

```bash
gcloud run services update SERVICE_NAME \
  --region=REGION \
  --update-env-vars MODEL_SERVICE_URL=https://YOUR-MODEL-SERVICE-URL.run.app
```

---

### Step 7 — Set secrets as environment variables

Sensitive values should be set via Cloud Run env vars (or Secret Manager), **not** committed to code:

```bash
gcloud run services update SERVICE_NAME \
  --region=REGION \
  --update-env-vars \
SUPABASE_URL=https://YOUR_PROJECT.supabase.co,\
SUPABASE_SERVICE_KEY=your-service-role-key,\
JWT_SECRET=your-long-random-secret,\
SMTP_HOST=smtp.gmail.com,\
SMTP_PORT=587,\
SMTP_USER=your-email@gmail.com,\
SMTP_PASS=your-app-password,\
SKIP_2FA=false
```

---

### Step 8 — Test the deployed service

```bash
# Get backend URL
gcloud run services describe SERVICE_NAME \
  --region=REGION \
  --format='value(status.url)'

# Health check
curl https://YOUR-BACKEND-URL.run.app/health

# API docs
open https://YOUR-BACKEND-URL.run.app/docs
```

---

### Files added for deployment

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image for the main FastAPI backend |
| `Dockerfile.model` | Container image for the ONNX model service |
| `.dockerignore` | Excludes secrets, venvs, local data from Docker builds |
| `cloudbuild.yaml` | Cloud Build pipeline: build → push → deploy both services |
| `.env.example` | Template for all required environment variables |

---

## Branch-Based CI/CD (GitHub -> Cloud Build -> Cloud Run)

### 1. Create and push `staging` branch

```bash
git checkout -b staging
git push -u origin staging
```

### 2. Connect GitHub repository to Cloud Build (one-time)

```bash
gcloud builds connections create github biometric-conn \
	--region=REGION

gcloud builds repositories create biometric-engine-repo \
	--remote-uri="https://github.com/YOUR_ORG_OR_USER/biometric-engine.git" \
	--connection="projects/PROJECT_ID/locations/REGION/connections/biometric-conn" \
	--region=REGION
```

### 3. Create Cloud Build trigger for staging CD

```bash
gcloud builds triggers create repository \
	--name="biometric-staging-cd" \
	--region=REGION \
	--repository="biometric-engine-repo" \
	--branch-pattern="^staging$" \
	--build-config="cloudbuild.yaml" \
	--substitutions="_PROJECT_ID=PROJECT_ID,_REGION=REGION,_REPOSITORY_NAME=REPOSITORY_NAME,_SERVICE_NAME=biometric-engine,_MODEL_SERVICE_NAME=biometric-model,_ENV=staging,_ALLOW_UNAUTH=true,_SUPABASE_URL_SECRET=supabase-url-staging,_SUPABASE_SERVICE_KEY_SECRET=supabase-service-key-staging,_JWT_SECRET_SECRET=jwt-secret-staging"
```

### 4. Create Cloud Build trigger for production CD

```bash
gcloud builds triggers create repository \
	--name="biometric-prod-cd" \
	--region=REGION \
	--repository="biometric-engine-repo" \
	--branch-pattern="^main$" \
	--build-config="cloudbuild.yaml" \
	--substitutions="_PROJECT_ID=PROJECT_ID,_REGION=REGION,_REPOSITORY_NAME=REPOSITORY_NAME,_SERVICE_NAME=biometric-engine,_MODEL_SERVICE_NAME=biometric-model,_ENV=prod,_ALLOW_UNAUTH=false,_SUPABASE_URL_SECRET=supabase-url-prod,_SUPABASE_SERVICE_KEY_SECRET=supabase-service-key-prod,_JWT_SECRET_SECRET=jwt-secret-prod"
```

### 5. Create CI trigger for pull requests (no deploy)

```bash
gcloud builds triggers create repository \
	--name="biometric-pr-ci" \
	--region=REGION \
	--repository="biometric-engine-repo" \
	--pull-request-pattern=".*" \
	--build-config="cloudbuild.ci.yaml"
```

### 6. Create required Secret Manager values

```bash
echo -n "https://YOUR_STAGING_PROJECT.supabase.co" | gcloud secrets create supabase-url-staging --data-file=-
echo -n "YOUR_STAGING_SUPABASE_SERVICE_KEY" | gcloud secrets create supabase-service-key-staging --data-file=-
echo -n "YOUR_STAGING_JWT_SECRET" | gcloud secrets create jwt-secret-staging --data-file=-

echo -n "https://YOUR_PROD_PROJECT.supabase.co" | gcloud secrets create supabase-url-prod --data-file=-
echo -n "YOUR_PROD_SUPABASE_SERVICE_KEY" | gcloud secrets create supabase-service-key-prod --data-file=-
echo -n "YOUR_PROD_JWT_SECRET" | gcloud secrets create jwt-secret-prod --data-file=-
```

If secrets already exist, add new versions with:

```bash
echo -n "NEW_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
```

### 7. Grant Cloud Build service account access to secrets and Cloud Run

```bash
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding PROJECT_ID \
	--member="serviceAccount:${CB_SA}" \
	--role="roles/run.admin"

gcloud projects add-iam-policy-binding PROJECT_ID \
	--member="serviceAccount:${CB_SA}" \
	--role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding PROJECT_ID \
	--member="serviceAccount:${CB_SA}" \
	--role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding PROJECT_ID \
	--member="serviceAccount:${CB_SA}" \
	--role="roles/secretmanager.secretAccessor"
```

### 8. CI/CD flow

- Push to `staging` branch -> builds + deploys `biometric-engine-staging` and `biometric-model-staging`
- Merge `staging` -> `main` -> builds + deploys `biometric-engine-prod` and `biometric-model-prod`
- Open PRs -> run CI image-build checks via `cloudbuild.ci.yaml`

