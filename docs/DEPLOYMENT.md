# CGAE Deployment Guide: Modal + Streamlit Cloud

## Architecture

```
┌─────────────────────┐
│  Streamlit Cloud    │  ← Dashboard (reads via HTTP)
│  (dashboard/app.py) │
└──────────┬──────────┘
           │
           │ HTTP GET
           │
┌──────────▼──────────┐
│  Modal Web Endpoint │  ← /get_results?path=...
│  (modal_deploy.py)  │
└──────────┬──────────┘
           │
           │ Reads from
           │
┌──────────▼──────────┐
│  Modal Volume       │  ← Persistent storage
│  /results/          │
└──────────▲──────────┘
           │
           │ Writes to
           │
┌──────────┴──────────┐
│  Live Runner        │  ← Long-running backend
│  (server.live_runner)│
└─────────────────────┘
```

## Step 1: Install Modal

```bash
pip install modal
modal setup
```

This opens a browser to authenticate with Modal.

## Step 2: Create Modal Secrets

```bash
# Azure OpenAI credentials
modal secret create azure-credentials \
  AZURE_API_KEY=your-key \
  AZURE_OPENAI_API_ENDPOINT=https://your-endpoint.openai.azure.com/

# Azure AI Foundry credentials
modal secret create azure-ai-credentials \
  DDFT_MODELS_ENDPOINT=https://your-foundry-endpoint/v1
```

Or create via Modal dashboard: https://modal.com/secrets

## Step 3: Deploy to Modal

```bash
# Deploy the app
modal deploy modal_deploy.py

# Or run locally (for testing)
modal run modal_deploy.py
```

This will:
1. Create a persistent volume `cgae-results`
2. Deploy the live runner as a long-running function
3. Deploy web endpoints for serving results

## Step 4: Get Your Modal Endpoints

After deployment, Modal will show:

```
✓ Created web function get_results => https://your-username--cgae-economy-get-results.modal.run
✓ Created web function list_results => https://your-username--cgae-economy-list-results.modal.run
```

Copy these URLs.

## Step 5: Update Dashboard for Modal

The dashboard needs to read from Modal's web endpoints instead of local files.

Create `dashboard/modal_loader.py`:

```python
import requests
import json
from pathlib import Path

MODAL_ENDPOINT = "https://your-username--cgae-economy-get-results.modal.run"

def load_from_modal(filename: str) -> dict:
    """Load a result file from Modal."""
    try:
        response = requests.get(f"{MODAL_ENDPOINT}?path={filename}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}
```

Then update `dashboard/app.py` to use this loader when deployed.

## Step 6: Deploy Dashboard to Streamlit Cloud

1. Push your code to GitHub
2. Go to https://share.streamlit.io
3. Click "New app"
4. Select your repo and `dashboard/app.py`
5. Add secrets in Streamlit Cloud settings:
   ```toml
   MODAL_ENDPOINT = "https://your-username--cgae-economy-get-results.modal.run"
   ```

## Step 7: Start the Backend

```bash
# Start the live runner on Modal
modal run modal_deploy.py
```

Or schedule it to run continuously:

```bash
modal deploy modal_deploy.py
```

The backend will run 24/7, writing results to the Modal volume.

## Monitoring

### Check backend logs:
```bash
modal logs cgae-economy
```

### Check available results:
```bash
curl https://your-username--cgae-economy-list-results.modal.run
```

### Get specific result:
```bash
curl "https://your-username--cgae-economy-get-results.modal.run?path=final_summary.json"
```

## Costs

**Modal:**
- Free tier: $30/month credit
- CPU: ~$0.0001/second
- Memory: ~$0.000001/GB-second
- Storage: $0.10/GB/month

**Estimated cost for 24/7 operation:**
- CPU (2 cores): ~$260/month
- Memory (4GB): ~$10/month
- Storage (1GB): $0.10/month
- **Total: ~$270/month** (covered by credits initially)

**Streamlit Cloud:**
- Free for public apps
- $20/month for private apps

## Alternative: Scheduled Runs

If 24/7 is too expensive, run on a schedule:

```python
@app.function(
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
    ...
)
def run_economy_batch():
    config = LiveSimConfig(num_rounds=10)  # Fixed rounds
    runner = LiveSimulationRunner(config)
    runner.run()
```

This reduces costs to ~$10/month.

## Troubleshooting

**Backend not starting:**
- Check logs: `modal logs cgae-economy`
- Verify secrets are set: `modal secret list`

**Dashboard not loading data:**
- Test endpoint: `curl https://your-endpoint.modal.run/list_results`
- Check CORS if needed (add to web_endpoint decorator)

**Volume not persisting:**
- Verify volume name matches: `modal volume list`
- Check mount path is `/results`

## Development Workflow

1. **Local testing:**
   ```bash
   python -m server.live_runner --rounds 5
   streamlit run dashboard/app.py
   ```

2. **Test on Modal:**
   ```bash
   modal run modal_deploy.py
   ```

3. **Deploy:**
   ```bash
   modal deploy modal_deploy.py
   ```

4. **Update dashboard:**
   ```bash
   git push origin main
   # Streamlit Cloud auto-deploys
   ```
