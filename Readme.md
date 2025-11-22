# QuotePilot

QuotePilot is an industrial instrumentation configuration and pricing engine.  
It builds and validates full part numbers using structured segment logic, applies price adders, and returns a complete quote including segment breakdowns.

The system is designed to scale across many instrument models, each with its own segment structure and pricing rules.

---

## Current Status (February 2025)

QuotePilot now supports:

### Multi-Model Engine System
The engine architecture allows any number of product models to register themselves automatically.  
Currently implemented:

* **QPSAH200S** Differential Pressure Transmitter  
* **QPMAG** Magnetic Flowmeter  

Each model includes:

* A master list of segments  
* Option codes and descriptions  
* Default configuration  
* Price adders  
* Full parsing and validation  
* Structured error handling  

Engines register via a decorator so the rest of the system discovers them automatically.

---

## Folder Structure

```
QuotePilot/
│
├── backend/
│   ├── api.py                   # FastAPI backend
│   ├── quote_ui.html            # Interactive browser UI
│   │
│   └── PartNumberEngine/
│        ├── base_engine.py      # Core engine, registry, error system
│        ├── __init__.py         # Auto-imports engines into the registry
│        ├── dp_qpsah200s.py     # QPSAH200S engine
│        └── qpmag_engine.py     # QPMAG engine
│
└── Docs/
    └── Example Price Sheet/
        └── QPSAH200S_SegmentPricing_Combined_v1.pdf
```

---

## FastAPI Backend

The backend provides a simple quoting API.

### Health Check  
```
GET /health
```

### List Available Engines  
```
GET /engines
```
Returns:

```
{
  "models": ["QPSAH200S", "QPMAG"]
}
```

### Quote Endpoint  
```
POST /quote
```

Example request:

```json
{
  "model": "QPSAH200S",
  "part_number": "QPSAH200S-A-M-G-3-C-3-1-1-C-1-02"
}
```

Response includes:

* Normalized part number  
* Segment breakdown  
* Base price and adders  
* Final price  
* Structured validation errors if any segment code is invalid  

---

## Web UI (quote_ui.html)

The UI shows:

* Model selector (auto-populated from backend)
* Autofilled default part numbers for each model
* A breakdown of every part-number segment
* Clear pricing summary
* Detailed structured errors

This UI is used for:

* Testing engines  
* Demonstrating part-number breakdown  
* Debugging invalid configurations  
* Previews for future public UX  

---

## Running Locally

From the `backend` folder:

```bash
uvicorn api:app --reload
```

Open your browser:

```
http://127.0.0.1:8000/ui
```

---

## Engine Architecture

Each engine subclass implements:

* `model`  
* `master_segments`  
* `default_part_number` (optional but recommended)  
* `quote()` method for:
  - parsing
  - validation
  - pricing
  - structured output  

The base engine handles:

* Registration system  
* Error handling (`PartNumberError`)  
* Engine discovery (`ENGINE_REGISTRY`)  

Adding a new model only requires creating a new engine file.

---

## Error Handling

All validation errors return:

```
{
  "ok": false,
  "error": "...",
  "segment": "Output signal type",
  "invalid_code": "Z",
  "valid_codes": ["A","B","C"]
}
```

This allows the UI or any client to highlight exactly where the part number is wrong.

---

## Future Roadmap

### Natural Language to Part Number  
Example user input:

> “I need a QPMAG with 150-lb flanges and standard everything else.”

QuotePilot will:

1. Identify the model  
2. Fill all default codes  
3. Override only the specified segments  
4. Produce a full validated part number  
5. Return pricing + breakdown  

### PDF Quote Generation  
Automatically produce a downloadable PDF quote with:

* Model info  
* Full part number  
* Segment breakdown  
* Pricing  
* Branding and terms  

### Authentication / API Keys  
Required for SAAS production use.

### Deployment  
Deploy full backend and UI to Railway under:

```
https://quotepilothq.com
```

---

## Summary

QuotePilot is now a complete, working, multi-model quoting engine with:

✓ Dynamic model discovery  
✓ Full segment parsing  
✓ Live UI  
✓ Autofilled defaults  
✓ Full breakdown display  
✓ Clean FastAPI backend  
✓ GitHub-ready architecture  

This is the foundation for the future AI-driven, natural language quoting system we will build next.
