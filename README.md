# VLESS Checker for Railway

Simple VLESS configuration checker with web service and Telegram reporting.

## Files
- `main.py` - Main script (all-in-one)
- `requirements.txt` - Dependencies (3 packages)
- `railway.json` - Railway configuration

## Environment Variables

### Required
- `VLESS_CONFIG` - VLESS configuration string

### Optional
- `MODE` - Operation mode: `web` (default), `telegram`, `check`
- `BOT_TOKEN` - Telegram bot token (for telegram mode)
- `CHAT_IDS` - Comma-separated chat IDs (for telegram mode)
- `PORT` - Web service port (default: 8000)

## Usage

### Web Service (default)
```bash
export VLESS_CONFIG="vless://uuid@host:port?params"
python main.py
```

### Telegram Reports
```bash
export MODE=telegram
export BOT_TOKEN="your_bot_token"
export CHAT_IDS="123456789,987654321"
export VLESS_CONFIG="vless://uuid@host:port?params"
python main.py
```

### Simple Check
```bash
export MODE=check
export VLESS_CONFIG="vless://uuid@host:port?params"
python main.py
```

## Railway Deployment

1. Push to GitHub
2. Create Railway project from repo
3. Set environment variables:
   ```
   VLESS_CONFIG=your_vless_config
   MODE=web
   ```
4. Railway auto-deploys

## API Endpoints (web mode)
- `GET /` - Service info
- `GET /health` - Health check
- `GET /check` - Run VLESS check

## What it checks
- DNS resolution
- Geolocation
- TCP connection
- HTTP connectivity
