"""Attempt the existing public-key path, then at most one ordinary provider reboot.

No password, alternate host key, disk operation or security-setting change.
The already reviewed SSH transport owns key creation and cleanup in its finally.
"""
import json
import subprocess
import time
import urllib.request

import timeweb_registered_ssh as registered
from observe_ssh_handshake import category

SERVER = 9417611
PROJECT = 2941515
API_SERVER = "/servers/9417611"
HEALTH = "https://analyst-ai-2941515.twc1.net/health"


def check_server(document, *, require_on):
    row = document.get("server", {})
    if (row.get("id") != SERVER or row.get("project_id") != PROJECT
            or row.get("availability_zone") != "ams-1" or row.get("cpu") != 4 or row.get("ram") != 8192):
        raise RuntimeError("unexpected_server_identity_or_hardware")
    if require_on and (row.get("status") != "on" or row.get("is_qemu_agent") is not True):
        raise RuntimeError("server_not_ready_for_graceful_reboot")
    if row.get("boot_mode") != "default":
        raise RuntimeError("normal_disk_boot_not_confirmed")
    return row.get("status") == "on"


def public_health():
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    try:
        with urllib.request.build_opener(NoRedirect()).open(HEALTH, timeout=5) as response:
            return response.status == 200 and response.geturl() == HEALTH
    except OSError:
        return False


def report(stage, **values):
    print("GUEST_KEY_RECOVERY=" + json.dumps({"stage":stage, **values}), flush=True)


class Resumption:
    def __init__(self, error_type, state, api, *, probe=subprocess.run, sleep=time.sleep,
                 clock=time.monotonic, health=public_health, normal_factory=registered.verified_remote):
        self.error = error_type
        self.state = state
        self.api = api
        self.probe = probe
        self.sleep = sleep
        self.clock = clock
        self.health = health
        self.normal = normal_factory(error_type, state, api)
        self.reboot_attempted = False
        self.handoff_ready = False

    def verify_assignment(self):
        identifier = self.state.get("id")
        if type(identifier) is not int or identifier < 1:
            raise RuntimeError("temporary_key_record_missing")
        status, document = self.api("GET", "/ssh-keys/" + str(identifier))
        if status != 200:
            raise RuntimeError("temporary_key_record_unavailable")
        if not registered.assignment(document, identifier, self.state.get("public")):
            raise self.error("key_not_yet_assigned_to_target")

    def ordinary_reboot(self):
        status, document = self.api("GET", API_SERVER)
        if status != 200:
            raise RuntimeError("server_metadata_unavailable")
        check_server(document, require_on=True)
        if not self.health():
            raise RuntimeError("pre_reboot_application_health_unknown")
        self.verify_assignment()
        # Set the latch BEFORE the request, including when the network drops
        # after the provider accepted it. Never retry an ambiguous POST.
        self.reboot_attempted = True
        status, _ = self.api("POST", API_SERVER + "/reboot")
        if status != 204:
            raise RuntimeError("ordinary_reboot_not_confirmed")
        report("ordinary_reboot_accepted", password_reset=False, boot_mode_changed=False)
        started = self.clock()
        deadline = started + 210
        healthy_after_settling = 0
        interrupted = False
        while self.clock() < deadline:
            self.sleep(6)
            status, document = self.api("GET", API_SERVER)
            ready = status == 200 and check_server(document, require_on=False) and self.health()
            if not ready:
                interrupted = True
            if ready and self.clock() - started >= 40:
                healthy_after_settling += 1
            else:
                healthy_after_settling = 0
            if healthy_after_settling >= 2:
                self.handoff_ready = True
                report("application_healthy", interruption_observed=interrupted)
                return
        raise RuntimeError("post_reboot_health_unconfirmed")

    def __call__(self, command, script, *, data=None, timeout=12):
        if script != "test $(id -u) = 0" or data is not None or timeout != 12:
            raise RuntimeError("unexpected_handshake_scope")
        if self.reboot_attempted:
            if not self.handoff_ready:
                raise RuntimeError("post_reboot_state_unverified")
            return self.normal(command, script, data=data, timeout=timeout)
        self.verify_assignment()
        attempt = self.probe(command+[script], input=None, capture_output=True, timeout=12)
        if attempt.returncode == 0:
            report("authenticated_without_reboot")
            return attempt.stdout
        if category(attempt.stderr) != "authentication_rejected":
            raise RuntimeError("reboot_not_appropriate_for_ssh_error")
        self.ordinary_reboot()
        return self.normal(command, script, data=data, timeout=timeout)


def main():
    # Only replace the authentication stage. Host pinning, registered key
    # checks, remote payload, credential cleanup and scope stay in the original.
    original_factory = registered.verified_remote
    registered.verified_remote = lambda error, state, api: Resumption(
        error, state, api, normal_factory=original_factory)
    try:
        registered.main()
    finally:
        registered.verified_remote = original_factory


if __name__ == "__main__":
    main()
