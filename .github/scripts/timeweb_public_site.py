"""Publish only static product files on the existing VDS, preserving API and database."""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import re
import shlex
from typing import Any

from timeweb_auth_postgres import EphemeralSsh, InfraError, find_managed_server, public_ipv4

# Run under the same deployment lock as the API release. No environment files,
# PostgreSQL, application service, provider provisioning or auth keys are touched.
REMOTE_PUBLISH = r'''
import base64, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.request
payload = json.load(sys.stdin)
sha = payload['sha']
if re.fullmatch('[a-f0-9]{40}', sha) is None:
    raise SystemExit('invalid_public_release')
base = pathlib.Path('/var/www/omnicio.ru/releases')
site = pathlib.Path('/etc/nginx/sites-available/omnicio.ru')
original = site.read_text()
root_pattern = r'root (' + re.escape(base.as_posix()) + r'/[a-f0-9]{40}(?:-public)?);'
roots = set(re.findall(root_pattern, original))
root_count = len(re.findall(root_pattern, original))
if len(roots) != 1 or original.count('root ') != root_count:
    raise SystemExit('unrecognized_public_root')
previous = pathlib.Path(roots.pop())
if previous.is_symlink() or not previous.is_dir() or base.is_symlink():
    raise SystemExit('untrusted_public_root')
def request(path):
    with urllib.request.urlopen('https://omnicio.ru' + path, timeout=10) as response:
        return response.read(4 * 1024 * 1024), response.headers
before, _ = request('/api/auth/config')
for path in ('/health/live', '/health/ready'):
    request(path)
target = base / (sha + '-public')
if target.is_symlink():
    raise SystemExit('untrusted_public_target')
# A retry may read back an already active immutable tree, but cannot overwrite it.
if target == previous:
    actual, _ = request('/')
    if hashlib.sha256(actual).hexdigest() != payload['root_sha256']:
        raise SystemExit('public_active_content_mismatch')
    print(json.dumps({'status':'public_site_ready','build':sha[:12],'api_unchanged':True}))
    raise SystemExit(0)
if target.exists():
    raise SystemExit('public_target_exists_inspect_before_retry')
target.mkdir(mode=0o755)
for name, encoded in payload['files'].items():
    path = pathlib.PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise SystemExit('invalid_public_path')
    destination = target / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(base64.b64decode(encoded, validate=True))
    destination.chmod(0o644)
# Existing legal documents remain coupled to the running auth API's versions.
for name in ('privacy.html','terms.html','consent.html'):
    source = previous / 'legal' / name
    if source.is_symlink() or not source.is_file():
        raise SystemExit('existing_legal_document_missing')
    (target / 'legal').mkdir(exist_ok=True)
    shutil.copyfile(source, target / 'legal' / name)
# Preserve any previously published installer and its signed-release metadata.
if (previous / 'downloads').is_dir():
    manifest = previous / 'downloads' / 'android.json'
    if manifest.is_file() and json.loads(manifest.read_text()).get('status') == 'published':
        shutil.copytree(previous / 'downloads', target / 'downloads',
                        dirs_exist_ok=True, symlinks=False)
changed = original.replace(previous.as_posix(), target.as_posix())
changed, count = re.subn(r'add_header X-Omnicio-Build "[a-f0-9]{12}";',
                        'add_header X-Omnicio-Build "'+sha[:12]+'";', changed)
if not count or 'proxy_pass http://127.0.0.1:8001;' not in changed:
    raise SystemExit('unrecognized_public_routing')
staging = site.with_name(site.name + '.public-new')
staging.write_text(changed)
staging.chmod(0o644)
try:
    os.replace(staging, site)
    subprocess.run(['nginx','-t'], check=True, capture_output=True)
    subprocess.run(['systemctl','reload','nginx'], check=True, capture_output=True)
    verified = False
    for attempt in range(6):
        body, headers = request('/')
        if (hashlib.sha256(body).hexdigest() == payload['root_sha256']
                and headers.get('X-Omnicio-Build') == sha[:12]):
            verified = True
            break
        time.sleep(1)
    if not verified:
        raise ValueError('public_readback_failed')
    for name in payload['files']:
        body, _ = request('/' + name)
        expected = (target / name).read_bytes()
        if hashlib.sha256(body).digest() != hashlib.sha256(expected).digest():
            raise ValueError('public_asset_mismatch')
    after, _ = request('/api/auth/config')
    if before != after:
        raise ValueError('api_identity_changed')
    for path in ('/health/live', '/health/ready'):
        request(path)
except BaseException:
    staging.write_text(original)
    os.replace(staging, site)
    subprocess.run(['nginx','-t'], check=True, capture_output=True)
    subprocess.run(['systemctl','reload','nginx'], check=True, capture_output=True)
    raise
print(json.dumps({'status':'public_site_ready','build':sha[:12],'api_unchanged':True}))
'''


def public_payload(root: pathlib.Path, sha: str) -> str:
    """Use the same installed-package renderer and unchanged brand as the full release."""
    from omnicio.web_assets import render_web_assets

    if re.fullmatch(r"[a-f0-9]{40}", sha) is None:
        raise InfraError("invalid_public_release")
    rendered = render_web_assets(root / "web", sha[:12])
    files = {name: value.encode() for name, value in rendered.items()}
    files["assets/brand/omnicio-logo.png"] = (root / "assets/brand/omnicio-logo.png").read_bytes()
    return json.dumps({
        "sha": sha, "root_sha256": hashlib.sha256(files["index.html"]).hexdigest(),
        "files": {name: base64.b64encode(value).decode() for name, value in files.items()},
    })


def publish_public_site(
    client: Any, *, root: pathlib.Path, sha: str, server_name: str, server_comment: str,
) -> None:
    """Only the already managed VDS is eligible; this function cannot create resources."""
    server = find_managed_server(client.get_servers(), name=server_name, comment=server_comment)
    if str(server["id"]) != "9235089":
        raise InfraError("unexpected_public_server")
    observed = client.get_server(9235089)
    payload = public_payload(root, sha)
    with EphemeralSsh(client=client, server_id=9235089, server_ip=public_ipv4(observed)) as ssh:
        result = ssh.run(
            "flock -w 60 /run/omnicio-auth-deploy.lock timeout --kill-after=5s 240s python3 -c "
            + shlex.quote(REMOTE_PUBLISH), input_text=payload, timeout=320,
        )
    if json.loads(result) != {"status": "public_site_ready", "build": sha[:12],
                              "api_unchanged": True}:
        raise InfraError("public_site_unverified")
