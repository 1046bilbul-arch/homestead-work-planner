#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
if [[ $EUID -eq 0 ]]; then echo "Run as your normal Pi user, not root"; exit 1; fi
if [[ "$ROOT" =~ [[:space:]] ]]; then echo "Use a path without spaces"; exit 1; fi
sudo apt-get update
sudo apt-get install -y python3-venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p data backups
chmod 700 data backups
if [[ ! -f .env ]]; then
  umask 077
  .venv/bin/python setup_credentials.py
fi
sudo tee /etc/systemd/system/work-planner.service >/dev/null <<EOF
[Unit]
Description=Homestead Work Planner
After=network.target
[Service]
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/waitress-serve --listen=127.0.0.1:8090 app:app
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
sudo tee /etc/systemd/system/work-planner-backup.service >/dev/null <<EOF
[Unit]
Description=Work Planner database backup
[Service]
Type=oneshot
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/python $ROOT/backup.py
UMask=0077
EOF
sudo tee /etc/systemd/system/work-planner-backup.timer >/dev/null <<EOF
[Unit]
Description=Daily Work Planner backup
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now work-planner.service work-planner-backup.timer
sudo systemctl restart work-planner.service
sudo systemctl status work-planner.service --no-pager
