# Deploying LinuxGuard on AWS EC2 (guide — not executed by the original build)

## 1. Launch the instance
Console → EC2 → Launch instance: Ubuntu Server 24.04 LTS, a small type (e.g. t3.micro — check current free-tier eligibility), create a key pair (`.pem`), default VPC.

## 2. Security Group (the firewall)
| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** only | admin access; never 0.0.0.0/0 |
| (none for 5000) | | | dashboard is reached through an SSH tunnel |

Optional direct access: add Custom TCP 5000 from **your IP/32** only, and change the compose port mapping to `"5000:5000"`. Prefer HTTPS via nginx/ALB for anything beyond a demo.

## 3. Connect and prepare Ubuntu
```bash
chmod 400 key.pem
ssh -i key.pem ubuntu@<EC2_PUBLIC_IP>
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get install -y git docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu && newgrp docker
```
## 4. Deploy
```bash
git clone https://github.com/<you>/LinuxGuard.git && cd LinuxGuard
cp .env.example .env
# replace the empty token line with a random one (keep this value private; never commit .env)
sed -i "s|^LINUXGUARD_API_TOKEN=.*|LINUXGUARD_API_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')|" .env
grep -c "^LINUXGUARD_API_TOKEN=.\+" .env      # should print 1
docker compose up -d --build
docker compose ps          # STATUS should become "healthy"
```
The token lets you change thresholds and (when set) protects the process/service endpoints; the dashboard has an **API token** button to enter it.

## 5. Test
```bash
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/overview
```
From your laptop: `ssh -i key.pem -L 5000:127.0.0.1:5000 ubuntu@<EC2_PUBLIC_IP>` then open http://localhost:5000.

## 6. Alternative: no Docker (systemd)
```bash
sudo useradd --system --home /opt/linuxguard linuxguard
sudo git clone <repo> /opt/linuxguard && cd /opt/linuxguard
sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo chown -R linuxguard /opt/linuxguard/data
sudo tee /etc/linuxguard.env <<< "LINUXGUARD_API_TOKEN=<token>"; sudo chmod 600 /etc/linuxguard.env
sudo cp deploy/linuxguard.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now linuxguard
journalctl -u linuxguard -f
```
In this mode LinuxGuard sees the real host's processes, disk and systemd services.

## 7. Secure remote access (recommended order)
1. **SSH tunnel** (above): nothing but SSH is exposed. Best for demos.
2. **Security Group rule for your IP only** + `"5000:5000"` in compose: HTTP is unencrypted, so the token and data cross the internet in clear text. Avoid for anything but short tests.
3. **HTTPS reverse proxy** (nginx + Let's Encrypt, or an ALB + ACM certificate) in front of the localhost-bound container, with the Security Group allowing 443 from known IPs.
Also: keep Ubuntu patched (`unattended-upgrades`), disable SSH password login (default on EC2), and **stop/terminate the instance when finished** to avoid charges.

## 8. Troubleshooting
- **SSH timeout:** Security Group lacks your *current* IP, or wrong public IP/key permissions (`chmod 400`).
- **Container unhealthy:** `docker compose logs linuxguard`.
- **Port in use:** `sudo ss -tulpn | grep 5000`.
- **Disk filling:** lower `LINUXGUARD_RETENTION_DAYS`; run `scripts/backup.sh`.
