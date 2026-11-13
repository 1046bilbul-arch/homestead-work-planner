# Pi deployment
Before installation check port 8090: sudo ss -ltnp | grep ':8090'
Clone to a separate directory under your home folder, then run bash install.sh as your normal user. Set a strong unique password when prompted. Do not commit .env, data or backups.
Cloudflare Tunnel: add planner.simplecontrol.store -> http://localhost:8090 on the existing tunnel if it runs on the Pi host. Protect the hostname with Cloudflare Access restricted to your email before exposing it. App login remains required. HTTPS is required for secure cookies and PWA installation. Check service status with systemctl status work-planner and curl http://127.0.0.1:8090/.
Daily SQLite backups are retained for 30 days in backups/. Copy backups off the Pi regularly. To restore, stop work-planner, preserve the existing database, copy a selected backup to data/planner.sqlite, then restart.
Update: git pull --ff-only, .venv/bin/pip install -r requirements.txt, sudo systemctl restart work-planner.
Current release is online-only for task data; offline task editing is not implemented.