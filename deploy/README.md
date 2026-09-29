# EC2 deployment

The application lives at `/home/ubuntu/projects/ns_phase_3` on the Ubuntu EC2 host and listens on port **8081**. The `campus-it` systemd service starts at boot and restarts after failures. One worker owns the SQLite connection. The existing application on port 8080 is untouched.

Python 3.12 and Node.js 22+ are required. Python packages are pinned in `requirements.txt`; Command Code CLI 1.66.0 is installed under `.venv/commandcode`. The protected, ignored `.env` selects live `commandcode_cli` with `stealth/space-bunny-alpha` and an application `API_TOKEN`. Model credentials never go into browser settings. Enter the application token under **Connection settings → API token → Connect**.

The server uses a repository-scoped read-only SSH deploy key for GitHub. To update after pushing:

```sh
cd ~/projects/ns_phase_3
git pull --ff-only origin main
/home/ubuntu/.local/campus-bootstrap/bin/uv pip install --python .venv/bin/python -r requirements.txt
API_TOKEN= .venv/bin/python -m unittest discover -s tests
node tests/test_browser_ids.cjs
sudo systemctl restart campus-it
curl -fsS http://127.0.0.1:8081/health
```

Use `sudo journalctl -u campus-it -n 50 --no-pager` for logs and `sudo systemctl status campus-it` for status. Persistent data is in `data/`; keep it and `.env` when updating. The test command clears the deployment access token only for the test process.

For public access, the instance's AWS security group must allow inbound TCP 8081 from the intended client IPs. Without that rule, use an encrypted SSH tunnel from your computer:

```sh
ssh -i ~/.ssh/technical_shree.pem -N -L 127.0.0.1:8081:127.0.0.1:8081 ubuntu@ec2-16-16-201-144.eu-north-1.compute.amazonaws.com
```

Then open `http://127.0.0.1:8081`. The tunnel protects the connection and works without exposing port 8081 publicly. Use HTTPS in front of the service before sending credentials over a public network.

Public visitors connect automatically when `PUBLIC_GUEST_ACCESS=1` and `API_TOKEN` is set in the server `.env`. The token remains server-side. Signed HttpOnly cookies select isolated visitor databases under `data/guests`; the admin bearer token still accesses the original workspace. Browser cookies retain visitor access for 30 days; clearing cookies starts a new workspace. Guest operations are serialized in this single-worker deployment.
