# Local financial research — operator record, 30 October 2026 (UTC)

**Installed is not running.** This is the existing Amsterdam VM, not a new server. The owner API remains on `68e0fb73feddf178c29d990633edae42aa7adda3`, APK 57. The full application source checkout prepared on the host is `853090e11dcefef693366159c97316e55045c4c9`. The isolated inference unit has not been activated. The application does not route reports to it yet. No trading or margin execution was enabled, no broker order or paid inference was sent in this rollout. No balance from a screenshot is treated as a live account reading.

| Observation | Evidence |
| --- | --- |
| Full source, checksum-verified 3,659,530,240-byte E4B file, isolated LiteRT 0.18.1 environment and required native libraries prepared on this VM | [Preparation](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41094102698) |
| Before the in-place upgrade: verified private online SQLite backup, integrity check OK, configuration, 108 previous source files and service definitions preserved | [Backup and exact resize](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41095586773) |
| Actual provider configuration: 4 vCPU, 8192 MiB RAM, 30720 MiB NVMe, no GPU; recurring account charge 7,960 RUB/month, conservative 31-day hourly estimate 8,087.28, excluding future variable charges | [Post-upgrade account read](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41096021700) |
| Public app and password-status endpoints responded HTTP 200 after resize. These probes are not a model or end-to-end owner login test | [Availability](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41096599869) |
| The provider reports a 1,000 Mbps public network. Sustained throughput, a monthly unlimited allowance and zero overage fees are not established | [VM network read](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41099416230), [provider's bandwidth unit](https://github.com/timeweb-cloud/terraform-provider-timeweb-cloud/blob/HEAD/docs/resources/server.md) |
| Two-thread E4B selected exact source excerpts in 12/12 synthetic tests; 3,827.93 MiB peak, 5.889–8.546 s. E2B failed the selector suite | [Selector qualification](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41088491694), [2,725 backend tests + 1,575 subtests](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41088491538) |
| First **reasoning** benchmark: real historical RUB/USD and TQBR/SBER close observations for June 6–7, 2024 from the CBR and MOEX. Both sources returned; nothing substituted. E4B with a 128-token reasoning budget, two threads: 2/6 questions had the correct conclusion AND exact citations (two correct abstentions); 25.18–32.90 s, 3,790.8 MiB. Application of this raw model as an autonomous financial analyst did not qualify | [Actual result and original public-input artifact](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41098946607) |
| Temporary deployment key existed, was assigned solely to the correct VM at all twelve attempts, and was rejected by guest SSH throughout five minutes; strict host identity was retained. The temporary key was removed. No remote activation script ran | [Bounded activation check](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41098570663), [10 transport/rollback tests](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41098399765) |

Model revision: `litert-community/gemma-4-E4B-it-litert-lm@e6a3892a8c22cf87ff99583996149cf3cb32452b`, weights SHA-256 `0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0`. Selector and reasoning results are different tasks. The 8 GiB upgrade allows a 5 GiB model cgroup with remaining memory for the app, OS and database; reaching that budget is not a reason to buy a GPU. No benchmark establishes the best general investment model or future returns.

The collector already checks primary sources for changes with per-source rate limits, revisions, source dates and stored originals. A 1 Gbit/s port can burst to a theoretical 125 MB/s; trying to fill it continuously would move around 324 TB per 30 days, before overhead. A maximum link rate is not a download requirement. Account reads stay in the broker adapter; the local model has no direct Internet access, shell, account secrets or ability to place orders. Updates to the evidence store do not update model weights. The existing paid route is Qwen3.5 Flash; a GPT-6 catalogue entry is not a successful paid reasoning test. Preserve 95 RUB/day and 2,900/month application caps within the owner's newer 11,000 infrastructure + 3,000 external AI budget.

## Restore guest management, then resume the prepared release

No further unattended SSH retries are scheduled. Use the **existing cloud VM's console** or an existing owner-managed SSH administrator session. Provider status reported the VM on and the guest agent enabled; this does not verify guest SSH configuration. Do not change the owner application password or send a private key, broker token, or raw owner environment in chat.

Review the OS's SSH/guest-agent services and actual login policy. Examples for the installed Linux family, from a trusted console:

```sh
sudo systemctl status ssh qemu-guest-agent --no-pager
sudo journalctl --utc -u ssh -u qemu-guest-agent --since '2026-10-30 17:24 UTC' --until '2026-10-30 17:31 UTC' --no-pager
sudo sshd -T | grep -E '^(pubkeyauthentication|permitrootlogin|authorizedkeysfile|authorizedkeyscommand|strictmodes) '
sudo namei -l /root/.ssh/authorized_keys
```

Use the effective configured authorized-keys path and any applicable SSH Match rules when diagnosing the failed login. Restore the intended public-key deployment mechanism only after establishing the guest-side cause. Do not enable password login, turn off host checking, grant the model root, or replace the running VM.

1. After guest access is repaired, rerun the [same activation](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/41098570663). It verifies real guest CPU/RAM and one retained official primary PDF before keeping the isolated worker running. Look for `LOCAL_RESEARCH_ACTIVE` and a successful run. An SSH banner, running service, or prior synthetic score alone is insufficient.
2. Only after that success, on the administrative branch run `.github/workflows/local-report-release.yml` if dispatch is available. Alternatively add/update `deploy/requests/local-report-route.json` with exactly the integer fields `activation_run` (41098570663) and `activation_attempt` (the actual successful attempt). Publishing this record does not itself submit such a request. No ticket is stored ahead of activation.
3. The release checks exact source, successful owner-laptop CI, clean Sonar, archive digest, the worker receipt in the guest and the healthy prior app. It installs only `local_research.py` and `osint_worker.py`, enabling the local route for relevant public reports. Existing services/source and the new flag are rolled back on failed post-checks. Only a successful `LOCAL_RESEARCH_ROUTE` receipt establishes that the application path is enabled.
4. After enabling, inspect processing of the next changed official report and sustained worker/API health on the host. A successful one-document smoke does not prove 24/7 reliability. Research does not toggle financial execution. The saved 0% loss-capacity figure and live executor were not changed.
