# FollowThru

Habit-building app with an iOS client and a FastAPI backend.

## Repository layout

- `ios/FollowThru`: iOS app project
- `app`: FastAPI backend
- `deploy`: EC2 deployment configuration

## Local development

### Backend

1. Copy `.env.example` to `.env` at the repo root and fill in your values:

   ```bash
   cp .env.example .env
   ```

2. Start the backend:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 app/run.py
   ```

   Health check: `GET http://127.0.0.1:8000/health`

### iOS

1. Open `ios/FollowThru/FollowThru.xcodeproj` in Xcode
2. Select the `FollowThru` scheme and a simulator
3. Run with `Cmd+R`

To run on a physical device, connect via USB, select the device in Xcode, and run.

### Backend tests

```bash
source .venv/bin/activate
pytest
```

---

## Deployment

### Infrastructure

The backend runs on an AWS EC2 instance (Amazon Linux 2023). The stack is:

- nginx reverse proxy on port 80 forwarding to FastAPI on port 8000
- systemd keeps the FastAPI process running and restarts it on failure
- SQLite database stored on the EC2 disk, persists across deploys
- An Elastic IP provides a permanent public address

### CI/CD

Pushing to `main` triggers a GitHub Actions workflow (`.github/workflows/deploy.yml`) that SSHes into the EC2 instance, pulls the latest code, reinstalls dependencies, restarts the service, and verifies the health check. No manual steps required for backend deploys.

The workflow requires three repository secrets set under Settings > Secrets > Actions:

- `EC2_HOST`: the server's public IP
- `EC2_USER`: the SSH user (`ec2-user`)
- `EC2_SSH_KEY`: the private key for SSH access

### iOS updates

iOS builds are not automated. To push an update to a device:

1. Pull latest: `git pull origin main`
2. Connect the device via USB
3. Build and install with `Cmd+R` in Xcode

### Server access

```bash
# SSH into the server
ssh -i ~/.ssh/followthru-keypair.pem ec2-user@<EC2_HOST>

# Check backend status
sudo systemctl status followthru

# View live logs
sudo journalctl -u followthru -f

# Restart backend
sudo systemctl restart followthru

# Open database
sqlite3 /opt/followthru/followthru.db
```

### Environment variables

The `.env` file lives at `/opt/followthru/.env` on the server and is never committed to git. Required variables:

```
DATABASE_URL=sqlite:///./followthru.db
SECRET_KEY=
JWT_SECRET=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

### API reference

- Health check: `GET http://<EC2_HOST>/health`
- Interactive API docs: `http://<EC2_HOST>/docs`
