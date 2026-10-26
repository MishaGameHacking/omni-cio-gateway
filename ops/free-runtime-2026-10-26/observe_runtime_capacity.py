"""Read current runtime capacity. No application imports or runtime mutations."""
import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import urllib.request


def main():
    assert os.geteuid() == 0
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
            memory[key] = int(value.split()[0]) * 1024
    services = {}
    allowed = {'ActiveState', 'SubState', 'NRestarts', 'MemoryCurrent', 'MemoryPeak', 'CPUUsageNSec'}
    for unit in ('analyst-ai-owner.service', 'analyst-ai-updates.service', 'caddy.service'):
        result = subprocess.run(['systemctl', 'show', unit, '--property=' + ','.join(sorted(allowed))],
                                capture_output=True, text=True, timeout=8, check=True)
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        assert set(values) <= allowed
        services[unit] = values
    timings = []
    for _ in range(3):
        start = time.monotonic()
        with urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5) as response:
            assert response.status == 200 and response.read(1024) == b'{"status":"ok"}'
        timings.append(round((time.monotonic() - start) * 1000, 2))
    latest = Path('/var/lib/analyst-ai-ops/latest-resource-sample.json')
    observation = {'available': False}
    if latest.exists():
        info = latest.lstat()
        assert stat.S_ISREG(info.st_mode) and not latest.is_symlink() and info.st_size <= 16384
        value = json.loads(latest.read_bytes())
        observation = {'available': True, 'sample_at_utc': value.get('at_utc'),
                       'sample_age_seconds': int(time.time()) - int(value['at']),
                       'cpu_busy_percent': value.get('cpu_busy_percent'), 'sqlite_bytes': value.get('sqlite_bytes')}
    disk = shutil.disk_usage('/var/lib/analyst-ai')
    print(json.dumps({'schema': 1, 'kind': 'runtime_capacity_readonly', 'runtime_server_id': 9417611,
        'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'memory_bytes': memory, 'load_average': list(os.getloadavg()),
        'disk_bytes': {'total': disk.total, 'used': disk.used, 'free': disk.free},
        'services': services, 'local_health_ms': timings, 'existing_sample': observation,
        'runtime_files_written': False, 'database_opened': False, 'services_restarted': False,
        'model_or_broker_calls': False, 'representative_load_test': False}, sort_keys=True))


if __name__ == '__main__':
    main()
