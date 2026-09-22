# Render deployment

Render's current FastAPI deployment flow uses a Web Service.

Build command:
pip install -r requirements.txt

Start command:
uvicorn backend.app:app --host 0.0.0.0 --port $PORT

The included render.yaml can be used as a Blueprint configuration.

Required secret:
API_FOOTBALL_KEY

Optional:
THESPORTSDB_KEY=123

After deployment, test:
/
 /health
 /docs
 /api/live
 /api/fixtures/today

Never commit real API keys into Git.
