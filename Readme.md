# QuotePilot

QuotePilot is a rules-based configuration and pricing engine for industrial instrumentation.

## Project Structure

backend/
    api.py                 FastAPI service exposing engine endpoints
    qp_dpt_engine.py       Parsing, validation, and pricing logic
    quote_ui.html          Simple browser UI for testing
    test_quote_api.py      External Python client for API testing
    __init__.py            Makes backend a Python package

## Endpoints

GET /health  
POST /quote  
GET /ui

## Running the API

cd backend  
uvicorn api:app --reload

## Testing

Browser UI:  
http://127.0.0.1:8000/ui

API docs:  
http://127.0.0.1:8000/docs

Python client:  
python test_quote_api.py
