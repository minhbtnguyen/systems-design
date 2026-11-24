# systems-design

- [url_shorterner](url_shorterner/README.md): design notes + FastAPI/SQLite implementation

## Run the URL shortener

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd url_shorterner/app
uvicorn main:app --reload
```

Server: http://localhost:8000. API docs: http://localhost:8000/docs.

```bash
curl -X POST localhost:8000/urls -H 'content-type: application/json' \
  -d '{"originalURL":"https://example.com"}'
```
