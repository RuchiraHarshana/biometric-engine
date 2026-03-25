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

