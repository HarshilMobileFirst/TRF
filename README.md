# TRF Scanner MVP

Backend-first MVP for scanning, extracting, validating, reviewing, correcting, and approving Test Requisition Forms using FastAPI, Streamlit, and local disk storage.

## What this includes

- FastAPI API with basic authentication
- Streamlit review console for upload, correction, and approval
- File-based storage only, no database
- Modular OCR, extraction, validation, and service layers
- OpenAI-powered OCR mode for document transcription
- Rule-based field extraction and validation
- Approved JSON output saved to local disk
- Unit tests for validation rules

## Folder structure

```text
trf_scanner/
├── app/
│   ├── api/routes/           # FastAPI route handlers
│   ├── core/                 # Config, auth, logging
│   ├── extraction/           # Rule-based field mapping
│   ├── ocr/                  # OCR interface and OpenAI provider
│   ├── schemas/              # Pydantic models
│   ├── services/             # File storage and workflow orchestration
│   ├── validators/           # Validation rules
│   └── main.py               # FastAPI app entrypoint
├── streamlit_app/            # Review and correction UI
├── storage/
│   ├── uploads/              # Original uploaded files
│   ├── processed/            # Initial extracted JSON
│   ├── corrected/            # Manually corrected JSON
│   └── approved/             # Approved final JSON
├── tests/                    # Unit tests
├── requirements.txt
└── README.md
```

## Architecture

The pipeline is intentionally modular:

1. `OCRProvider` extracts raw text from uploaded files.
2. `RuleBasedTRFMapper` maps OCR text into normalized TRF fields and confidence scores.
3. `TRFValidator` applies business rules and detects duplicates from saved local JSON files.
4. `TRFService` orchestrates file persistence and document state transitions.
5. Streamlit calls the API for listing, reviewing, correcting, validating, and approving TRFs.

## Extracted fields

The normalized JSON contains:

- `patient_name`
- `patient_id`
- `age`
- `gender`
- `doctor_name`
- `hospital_or_center_name`
- `requisition_date`
- `sample_type`
- `test_names`
- `test_codes`
- `priority`
- `contact_number`
- `notes`
- `source_file_name`
- `extraction_confidence`

Missing fields are returned as `null` or `[]`.

## Validation rules

The MVP includes rule-based validation for:

- Mandatory fields missing
- Invalid date format
- Invalid patient ID format
- Invalid phone format
- Unknown test code
- Mismatch between test name and test code
- Mismatch between test and sample type
- Duplicate test entries
- Suspicious duplicate requisition by checking saved JSON files
- Blank doctor or patient name
- Unsupported sample type

Validation returns:

```json
{
  "status": "review_required",
  "errors": [],
  "warnings": []
}
```

## Local setup

### 1. Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Python `3.12` is the safest choice for this MVP demo. Python `3.14` may fail on some machines if an older `pydantic-core` wheel is selected during dependency resolution.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Default credentials:

- Username: `admin`
- Password: `changeme`

## OpenAI model integration

This project now supports a real OpenAI-powered OCR path for demos.

Set these in `.env`:

```bash
OCR_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.1
```

In `openai` mode, the app sends uploaded TRF PDFs and images to an OpenAI multimodal model through the Responses API, asks it to produce a canonical TRF transcription, and then applies the local mapping and validation pipeline on top of that transcription.

For PDFs, the backend first uploads the file with the OpenAI Files API using `purpose=user_data`, then passes the returned `file_id` to the Responses API. This follows OpenAI's recommended PDF flow and is more reliable than inlining PDF bytes directly.

Each saved TRF JSON now includes:

- `extraction_provider`
- `extraction_model`

### 4. Run FastAPI

```bash
uvicorn app.main:app --reload
```

API docs will be available at `http://localhost:8000/docs`.

### 5. Run Streamlit

In another terminal:

```bash
streamlit run streamlit_app/app.py
```

The review UI will be available at `http://localhost:8501`.

### Streamlit Community Cloud

The Streamlit app runs on Streamlit’s servers. It **cannot** call `http://localhost:8000` on your laptop—that `localhost` is the Streamlit container, which is why you see **connection refused**.

1. Deploy the FastAPI app to a **public** HTTPS URL (Railway, Render, Fly.io, your own VPS, etc.).
2. In the Streamlit Cloud app: **Settings → Secrets**, add at least (**must be valid TOML**, not a raw shell `.env` unless you wrap it):

   ```toml
   TRF_API_BASE_URL = "https://your-api.example.com"
   TRF_UI_USERNAME = "admin"
   TRF_UI_PASSWORD = "same-as-backend-basic-auth"
   ```

   Pasting `KEY=value` lines without quotes can break TOML parsing, so the app may ignore them and keep using `localhost`. Either quote values as above, or put your whole `.env` inside a multiline `DOTENV = """ ... """` block (see [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)).

   `OPENAI_API_KEY` in Streamlit Secrets does **not** change where the UI sends HTTP requests; only **`TRF_API_BASE_URL`** (or aliases in the example file) points the Streamlit app at your deployed FastAPI.

   Redeploy or restart the Streamlit app after saving secrets.

Locally you can still use `TRF_API_BASE_URL=http://127.0.0.1:8000` in the environment when you run `streamlit run`.

## API endpoints

- `GET /health`
- `POST /trf/upload`
- `GET /trf`
- `GET /trf/{id}`
- `GET /trf/{id}/file`
- `POST /trf/{id}/validate`
- `PUT /trf/{id}/correct`
- `POST /trf/{id}/approve`

All `/trf` endpoints require HTTP Basic authentication.


## OpenAI references

This integration is based on the official OpenAI Responses API and file/image input guidance:

- https://platform.openai.com/docs/api-reference/responses
- https://platform.openai.com/docs/guides/images-vision
- https://platform.openai.com/docs/guides/pdf-files

## Running tests

```bash
pytest
```

## Example output

See [storage/processed/example_trf_output.json](storage/processed/example_trf_output.json) for a seeded example normalized JSON document.

## Future upgrade path

- Add non-OpenAI OCR backends (Tesseract, AWS Textract, Azure Document Intelligence, Google Document AI)
- Add richer duplicate detection and fuzzy matching
- Add PDF/image thumbnails and inline PDF rendering in the review UI
- Add audit history and a database when moving beyond MVP
