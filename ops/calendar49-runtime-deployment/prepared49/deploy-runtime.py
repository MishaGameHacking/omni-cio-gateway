"""Deploy exactly nine Windows-tested calendar/dispatch sources to the pinned owner service.

This payload is a future administrative action, not a local application runner.
It never imports the application, opens a database/configuration secret, installs
dependencies, calls trading/model endpoints, or publishes/installs an APK.
"""
from __future__ import annotations

import datetime
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

EXPECTED = {'schema': 1, 'source_backup_commit': '521d96293a048e4254bec936710bcfbf166b20a0', 'source_sha256': '8e4dc044ec6b700469a597cf8fc3a23aae96e57e5b5413e378dbf3986e2cef60', 'reviewed_manifest_sha256': 'd81252039e88864e5095670758b3148ec581b4b18f45eecd7ee8f4c7bad0b485', 'runtime_observation_sha256': 'e60238a67f01be52134c5d8cf0ac75e78f486118af03547931206ac5694b08cb', 'complete_source_sha256': '743a71819ec89d97467ce72189374a8070dd0fc3c6611710029b48f4feae8c23', 'base_commit': '6d037bcbba376d2b2e6e53caa0f96874ac1497ef', 'base_source_sha256': '26d1ccf6b9685925291edb968f17ef091b145831d7c6ca791e5e942246af49fa', 'github': {'run_id': 40453334023, 'run_attempt': 1, 'workflow_sha': '55b511a82ad9c2cce57d9d5cf01a3bfc741c1250', 'runner_name': 'omni-cio-ci-4'}, 'archive': {'bytes': 69716504, 'sha256': 'dc171704ffcf004aad7d8990408d301e9b3a63b6f030c0a5321e776cb7711fe4'}, 'archive_files': 1137, 'archive_path': '/var/lib/analyst-ai-build/incoming/windows-development-40453334023-1/windows-development-evidence.zip', 'runtime_sources': {'autonomous_ai.py': {'old': {'bytes': 53552, 'sha256': '789e338b462021f5d0274ae438638f54257111dbaadbee4dde090e130aa647cf'}, 'new': {'bytes': 54368, 'sha256': '09d0f79dc25c6e0a21af0f4aad81845ac11333f5338bb899666535ef990d2e53'}}, 'autonomous_controller.py': {'old': {'bytes': 35571, 'sha256': '926d10f0ee53b17a8c77fc90b6e7d07a8cf656f7e0ab9a3bb344fa063e3bbff5'}, 'new': {'bytes': 36417, 'sha256': '1930c63e307d45b86a68fad0506a34b069a5fdf68cef99a6ed1e8d17588fb56e'}}, 'volume_jobs.py': {'old': {'bytes': 18344, 'sha256': 'c18cb703f669ebfc431e8d20292f85851347cfd02c7ae451cea2c911a62e89c6'}, 'new': {'bytes': 19692, 'sha256': '4094b142b0f2b7522380e2d61bcb41a312493b5597bb1140f09a9a341ab5af06'}}, 'volume_workspace.py': {'old': {'bytes': 38845, 'sha256': '1b5e898823fa0dcdacf978fdd6023da4c9fb7c5ec5057513c277ef55263826a3'}, 'new': {'bytes': 39906, 'sha256': '3c034e056e8af731d5d78cffda95f892f92a4ad5cb0c11b0774a6636953ce08d'}}, 'volume_monitor.py': {'old': {'bytes': 14437, 'sha256': 'de762346ad2e504c7c9b28f2e97610241c6637b34cdd411ae4df21a5b5cbde6c'}, 'new': {'bytes': 14454, 'sha256': 'ae8ca8ab1fbadc9271a37eee0c04807d1429097b96a00254ec943ae89b514b86'}}, 'volume_market.py': {'old': {'bytes': 32918, 'sha256': '6b5883183634b4e23ed15413462bb7fd908c44092ded8bae7ebfc7f00c4b47ce'}, 'new': {'bytes': 33034, 'sha256': '5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'}}, 'market_schedule.py': {'old': None, 'new': {'bytes': 8958, 'sha256': '71fb3be626fb48856ec955a98a45b86023789e02060cd1bee79ab610c1abc1e1'}}, 'background_dispatch.py': {'old': None, 'new': {'bytes': 9212, 'sha256': 'eefe68f2ff91f7be346fc8026ad4e15296bc197d73379e5c7158ed295e7add25'}}, 'event_monitor.py': {'old': None, 'new': {'bytes': 8060, 'sha256': 'c5c853a1381369cfb0b95db922ec5d98536f261e727452970b2df6bdbc1378ad'}}}, 'calendar_contracts': {'test_market_schedule.py': {'names': ['test_explicit_broker_sunday_opens_only_read_only_polling', 'test_broker_holiday_overrides_an_ordinary_weekday', 'test_half_open_session_boundaries', 'test_known_auction_clearing_and_extra_windows_suspend_polling', 'test_stale_or_future_calendar_cannot_open_polling', 'test_missing_malformed_or_conflicting_evidence_stays_unknown', 'test_free_form_interval_is_not_relabelled_as_main_session', 'test_previous_utc_day_window_crosses_midnight_without_guessing_a_weekday', 'test_overlapping_day_windows_are_not_silently_chosen', 'test_every_required_section_must_be_present_and_in_its_window', 'test_unknown_instrument_exchange_has_no_substituted_venue', 'test_cash_only_bootstrap_uses_moex_but_requires_actual_schedule', 'test_naive_dispatch_clock_is_rejected'], 'count': 37, 'source': {'bytes': 7131, 'sha256': '49987f384987d15f82bb878c52d49f711c35032bcaa3fbad84abe561bae87cc6'}}, 'test_background_dispatch.py': {'names': ['test_closed_market_still_schedules_events_with_zero_model_budget', 'test_unknown_calendar_keeps_event_lane_and_blocks_automatic_prices', 'test_first_connection_can_bootstrap_once_without_a_calendar', 'test_open_window_schedules_due_prices_but_not_every_tick', 'test_event_job_keeps_prices_and_accounting_times_and_updates_event_freshness', 'test_event_source_failure_preserves_other_sources_and_acknowledged_cursor', 'test_concurrent_newer_snapshot_cannot_be_overwritten_by_event_commit', 'test_reconnection_rejects_queued_old_event_work_before_source_access', 'test_pause_cancels_automatic_events_without_cancelling_manual_refresh', 'test_automatic_analysis_rechecks_closure_at_execution_before_broker_or_model', 'test_manual_request_coalescing_removes_only_its_automatic_calendar_restriction', 'test_automatic_collection_rechecks_calendar_after_waiting_in_queue', 'test_event_compare_and_swap_detects_changes_with_same_snapshot_id', 'test_calendar_and_event_status_are_read_only_and_survive_in_memory_reset', 'test_queue_priority_aging_and_reconciliation_order', 'test_new_events_precede_background_work_but_preserve_per_user_lease', 'test_expired_event_worker_preserves_its_checkpoint_and_receives_new_owner', 'test_failure_or_full_queue_for_one_user_does_not_abort_other_dispatch_lanes'], 'count': 18, 'source': {'bytes': 16011, 'sha256': '2ec1d86e7497ddac9de4c8adbc32caa0c6eba9808ee1497be84d4bda46ac6fbb'}}}, 'calendar_test_count': 55, 'callback_style_sha256': 'd20328944ed84302094181fdffee0b5d79522034eb8af980f487382ddebef40a', 'services': {'analyst-ai-owner.service': {'active_state': 'active', 'effective_dropins_present': False, 'expected_fragment_path': True, 'invocation': {'argument_count': 12, 'executable': '/opt/analyst-ai/venv/bin/uvicorn', 'module': 'owner_app:create_app', 'options': {'--factory': True, '--host': '127.0.0.1', '--lifespan': 'on', '--no-access-log': True, '--port': '8080', '--workers': '1'}, 'owner_factory_binding_verified': True, 'public_update_factory_binding_verified': False, 'source_path': '/opt/analyst-ai/backend/owner_app.py', 'status': 'allowlisted_invocation_observed'}, 'load_state': 'loaded', 'matches_prior_unit_identity': True, 'need_daemon_reload': 'no', 'status': 'observed', 'unit_file_identity': {'bytes': 923, 'sha256': '7df9096fbc578716208077355fa8ac4cbc5c1480844e83910bfa7a0b40c06ed0', 'status': 'observed'}, 'working_directory': '/opt/analyst-ai/backend', 'working_directory_allowlisted': True}, 'analyst-ai-updates.service': {'active_state': 'active', 'effective_dropins_present': False, 'expected_fragment_path': True, 'invocation': {'argument_count': 13, 'executable': '/opt/analyst-ai-updates/venv/bin/python', 'module': 'backend.public_updates_app:create_app', 'options': {'--factory': True, '--host': '127.0.0.1', '--no-access-log': True, '--port': '8081', '--workers': '1'}, 'owner_factory_binding_verified': False, 'public_update_factory_binding_verified': True, 'source_path': '/opt/analyst-ai-updates/backend/public_updates_app.py', 'status': 'allowlisted_invocation_observed'}, 'load_state': 'loaded', 'matches_prior_unit_identity': True, 'need_daemon_reload': 'no', 'status': 'observed', 'unit_file_identity': {'bytes': 893, 'sha256': '98a5a053ccdbb37938b7cac9bcba937da09cdcd828f913ec2750e01d0bc95cc9', 'status': 'observed'}, 'working_directory': '/opt/analyst-ai-updates', 'working_directory_allowlisted': True}}, 'units': {'/etc/systemd/system/analyst-ai-owner.service': {'bytes': 923, 'sha256': '7df9096fbc578716208077355fa8ac4cbc5c1480844e83910bfa7a0b40c06ed0'}, '/etc/systemd/system/analyst-ai-updates.service': {'bytes': 893, 'sha256': '98a5a053ccdbb37938b7cac9bcba937da09cdcd828f913ec2750e01d0bc95cc9'}}, 'active_caddy': {'bytes': 933, 'sha256': '57192fc11c94c8691c036d6208ce20ab429a5af7047ea17f3432498212db3041'}, 'caddy_file': {'bytes': 501, 'sha256': '01f467fb00ccb6034bb98e82bb59e405ac9e33b241ecaf472e4d844fcfbf262e'}, 'untouched_sources': {'/opt/analyst-ai-updates/backend/public_updates_app.py': {'bytes': 1219, 'sha256': '65223e183ab426c2e9fb7619e97aa321f6a9b9c1e4f72392ee8b4fe056edf0d8'}, '/opt/analyst-ai/backend/ai_budget.py': {'bytes': 11358, 'sha256': '7fa2a785f26e1227252c8785f1e12029192b093ad2809a020f1cd647f7bcf947'}, '/opt/analyst-ai/backend/ai_guarded_client.py': {'bytes': 16889, 'sha256': '349f89534b0e562aaf84a6bdbce9db28db5a9719cd3682ba3bf23daaec2d59ae'}, '/opt/analyst-ai/backend/ai_jobs.py': {'bytes': 10904, 'sha256': '38205417d64d14847620a4f45a2a20ad1f0d7cd5bab512c1feca8bfd53a45194'}, '/opt/analyst-ai/backend/ai_policy.py': {'bytes': 5269, 'sha256': '44cfdcdf2d862a681287f2a20dc387051fe227dcb2c68d5d18247d349a714fa9'}, '/opt/analyst-ai/backend/ai_route_catalog.py': {'bytes': 4865, 'sha256': 'a88981df52942a4c08fd60018aabf333ceaa85e8c4db8e79930f75b5e9e5a3c9'}, '/opt/analyst-ai/backend/allocation_plan.py': {'bytes': 14103, 'sha256': '90f3396a685ef9968c30fa5c5c1f7acfb9983825993d4c0b9b68710ce07fd4ad'}, '/opt/analyst-ai/backend/analysis_engine.py': {'bytes': 11660, 'sha256': '2700fdde343666a6e2441a943fb11dac2a5ea3906c04520b90c2b2721bde22e1'}, '/opt/analyst-ai/backend/android_runtime_contract.py': {'bytes': 3142, 'sha256': '1ed9a56769d308c9f5457fa383517a80965cd474dff8851e16a85390954335c2'}, '/opt/analyst-ai/backend/app.py': {'bytes': 29265, 'sha256': '33950c712e6442ce00af8de84f1e2c174c75d140728c1c093f00d717f5948c40'}, '/opt/analyst-ai/backend/automation_ui_evidence.py': {'bytes': 8099, 'sha256': '4a06b75ba342d80f7bcee6d0fbbb985d6562d390deb147438c04c48be91ae35c'}, '/opt/analyst-ai/backend/bounded_ai_response.py': {'bytes': 4723, 'sha256': '95d51fa2f6a2c6190ae572a2c88cf13ca2803af999d9a77ddfd908c6c397db14'}, '/opt/analyst-ai/backend/broker_connections.py': {'bytes': 6568, 'sha256': 'd0e4079f030ccc466da0b5224478a75841c02cfbf17a1151286a5f56845f5651'}, '/opt/analyst-ai/backend/client_compatibility.py': {'bytes': 2245, 'sha256': 'cf585f4a740198325e47166b318f12c41017491e34edb27c5511c53790a7d8e9'}, '/opt/analyst-ai/backend/client_diagnostics.py': {'bytes': 8863, 'sha256': '6316faa45abc793adb16fb6d8b42993e2c778e9411e31ed525c1742c379e1bc0'}, '/opt/analyst-ai/backend/client_updates.py': {'bytes': 13743, 'sha256': '79c1f8670cc61f94f917c9ad4b6e394f1430a08b61b8ef87216624fec12b9184'}, '/opt/analyst-ai/backend/credit_evidence.py': {'bytes': 15694, 'sha256': '96af887aa723e8e74e7d037f4785da532d6aa16ef6916eaf099c0ba847b4fd80'}, '/opt/analyst-ai/backend/evidence_history.py': {'bytes': 3273, 'sha256': 'e9f16324ac661abfcd4c8ee6e6deaa7b7748245891e8c5c5c15d02c63a28ce12'}, '/opt/analyst-ai/backend/evidence_order.py': {'bytes': 3041, 'sha256': '46368a7a78a2fbfc55198e222795abe977c490c3f07703ddcb8f4afd2f45f2d7'}, '/opt/analyst-ai/backend/evidence_revision.py': {'bytes': 3100, 'sha256': '7fa8f33904ac8f363f7eaddbba29ff9942ce7e1e4ad958ad23fc1185852876c4'}, '/opt/analyst-ai/backend/installation_evidence.py': {'bytes': 8652, 'sha256': '04e13002c8b5e5046a86e3a5e8de1edc354888eb581202f010ee992563468c3c'}, '/opt/analyst-ai/backend/investment_chat_policy.py': {'bytes': 9474, 'sha256': '65130e31014142a968546beeebd58d93422c7f7ff027b34f587a890002f529f2'}, '/opt/analyst-ai/backend/investment_links.py': {'bytes': 1418, 'sha256': '55d7d36ab4847509fde4e1e46dcc6811b215d2b07ddbb5c5ada22a7ce4dd0688'}, '/opt/analyst-ai/backend/model_json_limits.py': {'bytes': 2324, 'sha256': '2cd9d1f126965ee947b25ee0a5fb82ec5e43b018c5040cd6871b76ca9af7a1ae'}, '/opt/analyst-ai/backend/monitoring_access.py': {'bytes': 1772, 'sha256': '9c6156d1452db85c8adad877e8d9ffe336f499cb44752174e9761a01881fa6cc'}, '/opt/analyst-ai/backend/owner_access.py': {'bytes': 6178, 'sha256': '5bd31e342cea7dbbf1814874a8702140d5669534cd2948c33982b319beee78d3'}, '/opt/analyst-ai/backend/owner_app.py': {'bytes': 5798, 'sha256': '09dda073a447e12f742e4540945e1695be14ce943cf9471189cf4ca80c3d729b'}, '/opt/analyst-ai/backend/portfolio_details.py': {'bytes': 29229, 'sha256': 'd677d2d74f1761b53c507ae716da29d7312f7c526e99a873686008e6ba986a57'}, '/opt/analyst-ai/backend/portfolio_mandate.py': {'bytes': 4743, 'sha256': 'a8647933e107a3e1427438999b266869ae9be456786710cea56f997d57459c78'}, '/opt/analyst-ai/backend/portfolio_research.py': {'bytes': 20571, 'sha256': '6f657312995316d157424319e75ed876c9d567f52e7a0d267fc30266fac87b70'}, '/opt/analyst-ai/backend/portfolio_risk.py': {'bytes': 23821, 'sha256': 'b796b20085311a6318436c263abe66068dfe8e75e844e6329beec20cc670ce43'}, '/opt/analyst-ai/backend/portfolio_scenarios.py': {'bytes': 7489, 'sha256': '64d2a12e69b5d1dd482d2148d222d1f717b4f04ef6a5218da8357d82faf438ec'}, '/opt/analyst-ai/backend/public_updates_app.py': {'bytes': 1219, 'sha256': '65223e183ab426c2e9fb7619e97aa321f6a9b9c1e4f72392ee8b4fe056edf0d8'}, '/opt/analyst-ai/backend/purchase_policy.py': {'bytes': 12689, 'sha256': '53a264d7d091125c759b1d0cbf7d49542be3e27ca44c3661ea56b3d03aec0040'}, '/opt/analyst-ai/backend/release_bytes.py': {'bytes': 1807, 'sha256': '71de304be624aed78b53966c66c863aef41d6c961c92badea1f399cd07785ac5'}, '/opt/analyst-ai/backend/release_contract.py': {'bytes': 5885, 'sha256': 'dd6bcbf3c3802dd47003657ee13c548270b0e992cb210fdb3bc2727572d4d933'}, '/opt/analyst-ai/backend/release_json.py': {'bytes': 4285, 'sha256': '04a760b02105322f41d400cbdd6d44a4519c4e8dcd03ffd53fcd6da5fadf6b97'}, '/opt/analyst-ai/backend/release_lock.py': {'bytes': 1638, 'sha256': '548c06b4d8bcc9323eb5e1d49ef17fe4f8689967c2240fd1710653bcab08ce74'}, '/opt/analyst-ai/backend/release_publication.py': {'bytes': 10167, 'sha256': '9f083c508dbfc1e34721e6379044d2071c6e0752029f739e7280a9c65cb6a914'}, '/opt/analyst-ai/backend/research_clock.py': {'bytes': 3137, 'sha256': '267d22a868657d288c89d286ec9007ebf3d01ce25e486f718c5aabbcdf612d70'}, '/opt/analyst-ai/backend/research_import.py': {'bytes': 7893, 'sha256': '806548c1c80d087c3cefe29f9181678f1257faa29760f02ff60e2f57b8e34e4f'}, '/opt/analyst-ai/backend/research_profile_cache.py': {'bytes': 554, 'sha256': '20cb8cd5533dd63ae414ea383dfd1221476762e583e21a67b39602cf5bca3d23'}, '/opt/analyst-ai/backend/research_snapshot.py': {'bytes': 3527, 'sha256': '6971a39d7ba336d3f57b9ec166f61b1687669bc7ec10e982f2473e520da82252'}, '/opt/analyst-ai/backend/research_store.py': {'bytes': 9508, 'sha256': '703b1a251bf3bbae73b8b82bf7647d19a45f3eb0951887bb9822adcc59d5b874'}, '/opt/analyst-ai/backend/risk_math.py': {'bytes': 13842, 'sha256': 'f2492cbbbb7750099b74c5a0564a497d21fef5ffe413971690fe62fb2d049c5c'}, '/opt/analyst-ai/backend/risk_preview.py': {'bytes': 11526, 'sha256': '295a41d0495440366c4cef2aa5f89c6bde5a138e63f269ad7b2b1e050927f82c'}, '/opt/analyst-ai/backend/telegram_browser_app.py': {'bytes': 16927, 'sha256': '5a1ef0f644948cad8d38b4537b9b5c938582fea79955c143453c797b67c46793'}, '/opt/analyst-ai/backend/telegram_oidc.py': {'bytes': 5217, 'sha256': '3d7e64b50811b4b1ff70ec2512f1895f493de77932814976e87e0e509322b3a8'}, '/opt/analyst-ai/backend/timeweb_ai.py': {'bytes': 9066, 'sha256': 'e473a8cddb469b3f5b0a4290fb003d94e03ebb8e960de914406e84e24f7c59a3'}, '/opt/analyst-ai/backend/tinvest_portfolio.py': {'bytes': 16296, 'sha256': '6213499c73fb69b76ddd09a50f4f3a3eb4ac95e42965416d907b201b0711f754'}, '/opt/analyst-ai/backend/volume.py': {'bytes': 630, 'sha256': '2efb14fb95452af54a91899f9b7d3b8dcef694026493eb1061e34e7906e79741'}, '/opt/analyst-ai/backend/volume_analysis.py': {'bytes': 7324, 'sha256': '398c8955a399b7c55eda1939f6cfc5f2c2a137f2a844351f8a8c0cb1931e63cc'}, '/opt/analyst-ai/backend/volume_catalogue.py': {'bytes': 5085, 'sha256': 'f205f57a01804ef79d67e838db832ec62f5cf0353fafff6ed7fb43c0e1aa6e1b'}, '/opt/analyst-ai/backend/volume_chat.py': {'bytes': 44737, 'sha256': '0d258ed870086bbf47ac6747c62484b265a6784bf307f740262acf2d30591c66'}, '/opt/analyst-ai/backend/volume_contract.py': {'bytes': 8050, 'sha256': 'e00250093544aec09f78d86afa597db7aaec690921fc6c90dad6ce01f26a2a41'}, '/opt/analyst-ai/backend/volume_credit.py': {'bytes': 4722, 'sha256': '13a868cf49a848849d68b7f79ee607d7f29318d1fd97ba5c8e35495582cdea41'}, '/opt/analyst-ai/backend/volume_devices.py': {'bytes': 3348, 'sha256': '68440c1b92d81d72d4e01dc16731fa76f4637647e221cb846e0ba67fe08d10dd'}, '/opt/analyst-ai/backend/volume_impact.py': {'bytes': 11925, 'sha256': '38d91ef35eb5e1c850fe64d5ea32c4f9cdd7a501137d0cb922af9a51d4a51d82'}, '/opt/analyst-ai/backend/volume_live.py': {'bytes': 8495, 'sha256': 'be782c7cb5c078edbd9693a72909c3b0b455fb73ebe066516f21fe352c9b8b2a'}, '/opt/analyst-ai/backend/volume_news.py': {'bytes': 6801, 'sha256': '355d506a59d43089ba4dc4326a3a3fbd6bb009180afecc4be67318b25e01bc57'}, '/opt/analyst-ai/backend/volume_notifications.py': {'bytes': 16328, 'sha256': '74752d772493b173cd33c0cdf207f9d52f2d30c55ffdc78bedd3e68994e9885d'}, '/opt/analyst-ai/backend/volume_plans.py': {'bytes': 16128, 'sha256': '54bd52e549ae5fac4af52a01f0d4515710042383a34207e22f3d591a106ec88e'}, '/opt/analyst-ai/backend/volume_purchases.py': {'bytes': 14574, 'sha256': '21c5db4e53222f8b813e7da22115338f0c8c00dc4149ec0ac0677037cb2aaabe'}, '/opt/analyst-ai/backend/volume_state.py': {'bytes': 41301, 'sha256': '0aeea80a5043a936619a302c415455542f0b7c7ddc62a8179c33a753823779bd'}}, 'build_report': {'bytes': 29025, 'sha256': '7af8b02af5070253d69b38734372f59d5f47e40961300122aca6e904a89459f0'}, 'build_controller': {'bytes': 443, 'sha256': '8a8a60b8fb51c254b0b8aa5b929f49d6a78607880018e0be4de8bc9085ecd906'}, 'source_inventory': {'bytes': 169864, 'sha256': 'fdfd3d0fad9835210fd122115dc8ea4ecc292c2fbb3e60d518242bda8ad812b4'}}
SOURCE_ROOT = Path('/opt/analyst-ai/backend')
STORE = Path('/opt/analyst-ai/.calendar49-runtime-deployment')
SERVICES = ('analyst-ai-owner.service', 'analyst-ai-updates.service')
WORKDIRS = frozenset(('/opt/analyst-ai', '/opt/analyst-ai/backend', '/opt/analyst-ai-updates'))
MODULES = frozenset(('owner_app:create_app', 'backend.owner_app:create_app', 'app:app', 'backend.app:app',
                    'telegram_browser_app:app', 'backend.telegram_browser_app:app',
                    'backend.public_updates_app:create_app', 'public_updates_app:create_app'))
EXECUTABLES = frozenset(root + '/venv/bin/' + name for root in ('/opt/analyst-ai', '/opt/analyst-ai-updates')
                       for name in ('python', 'python3', 'uvicorn'))
PROPERTIES = ('ExecStart', 'WorkingDirectory', 'FragmentPath', 'DropInPaths',
              'LoadState', 'ActiveState', 'NeedDaemonReload')

class ObservationError(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise ObservationError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(raw):
    return {'bytes': len(raw), 'sha256': digest(raw)}


def stable(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def trusted_read(path, maximum):
    need(path.is_absolute() and path == Path(PurePosixPath(path).as_posix()), 'noncanonical_fixed_path')
    for parent in reversed(path.parents):
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
             and info.st_uid == 0 and not info.st_mode & 0o022, 'untrusted_parent')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
         and not before.st_mode & 0o022 and 0 < before.st_size <= maximum, 'untrusted_or_oversized_file')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        need(stable(os.fstat(stream.fileno())) == stable(before), 'file_changed_before_read')
        raw = stream.read(maximum + 1)
        need(len(raw) == before.st_size and len(raw) <= maximum
             and stable(os.fstat(stream.fileno())) == stable(before) == stable(path.lstat()),
             'file_changed_during_read')
    return raw


def observed_file(path, maximum):
    try:
        raw = trusted_read(path, maximum)
        return {'status': 'observed', **identity(raw)}, raw
    except FileNotFoundError:
        return {'status': 'absent'}, None
    except (ObservationError, OSError, ValueError):
        return {'status': 'bounded_read_unavailable'}, None


def unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, 'duplicate_json_key')
        value[key] = item
    return value


def active_caddy():
    connection = http.client.HTTPConnection('127.0.0.1', 2019, timeout=5)
    try:
        connection.request('GET', '/config/', headers={'Accept': 'application/json'})
        response = connection.getresponse()
        raw = response.read(2 * 1024**2 + 1)
        need(response.status == 200 and 0 < len(raw) <= 2 * 1024**2, 'active_caddy_unavailable')
        value = json.loads(raw, object_pairs_hook=unique)
        need(type(value) is dict and type(value.get('apps', {}).get('http', {}).get('servers')) is dict,
             'active_caddy_schema_unavailable')
        return {'status': 'observed', **identity(raw)}, value
    except (ObservationError, OSError, ValueError, http.client.HTTPException):
        return {'status': 'bounded_active_configuration_unavailable'}, None
    finally:
        connection.close()


def bounded_systemctl(name):
    need(name in SERVICES, 'unexpected_service')
    command = ['systemctl', 'show', name, '--no-pager', *('--property=' + key for key in PROPERTIES)]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, close_fds=True)
    raw = bytearray()
    deadline = time.monotonic() + 6
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                need(remaining > 0 and selector.select(remaining), 'systemctl_observation_timeout')
                chunk = os.read(process.stdout.fileno(), min(4096, 65537 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                need(len(raw) <= 65536, 'systemctl_observation_exceeds_bound')
        need(process.wait(timeout=max(0.1, deadline - time.monotonic())) == 0, 'systemctl_observation_failed')
    finally:
        if process.poll() is None:
            process.kill()  # Only this observer's systemctl show process, never a service.
        process.wait(timeout=2)
        process.stdout.close()
    lines = bytes(raw).decode('utf-8').splitlines()
    values = {}
    for line in lines:
        key, separator, value = line.partition('=')
        need(separator and key in PROPERTIES and key not in values, 'unexpected_systemctl_schema')
        values[key] = value
    need(set(values) == set(PROPERTIES), 'incomplete_systemctl_schema')
    return values


def invocation(value, working_directory, service):
    """Return only finite, recognized argv fields; never echo an unknown argument."""
    result = {'status': 'invocation_not_understood', 'owner_factory_binding_verified': False,
              'public_update_factory_binding_verified': False, 'source_path': None}
    # systemctl show emits structured ExecCommand entries. Multiple commands,
    # escaped values and unrecognized options cannot become a verified binding.
    match = re.fullmatch(r'\{ path=([^;\r\n]+) ; argv\[\]=([^\r\n]+?) ; ignore_errors=(?:yes|no) ; [^\r\n]* \}', value)
    if match is None or value.count('{ path=') != 1:
        return result
    executable, arguments = match.groups()
    if executable not in EXECUTABLES or any(c in arguments for c in ('\\', '\n', '\r', '{', '}')):
        return result
    try:
        argv = shlex.split(arguments, posix=True)
    except ValueError:
        return result
    if not 1 <= len(argv) <= 40 or argv[0] != executable:
        return result
    result.update(executable=executable, argument_count=len(argv))
    tail = argv[1:]
    if executable.rsplit('/', 1)[-1] in {'python', 'python3'}:
        while tail and tail[0] in {'-B', '-u'}:
            tail = tail[1:]
        if tail[:2] != ['-m', 'uvicorn']:
            return result
        tail = tail[2:]
    if not tail or tail[0] not in MODULES:
        return result
    module, tail = tail[0], tail[1:]
    result['module'] = module
    options = {}
    flags = {'--factory', '--no-access-log', '--access-log', '--no-server-header',
             '--server-header', '--proxy-headers', '--no-proxy-headers'}
    finite = {'--host': {'127.0.0.1', 'localhost'}, '--port': {'8080', '8081'},
              '--workers': {'1'}, '--lifespan': {'on', 'auto', 'off'},
              '--log-level': {'critical', 'error', 'warning', 'info', 'debug', 'trace'},
              '--app-dir': WORKDIRS, '--forwarded-allow-ips': {'127.0.0.1'}}
    while tail:
        token, tail = tail[0], tail[1:]
        if token in flags and token not in options:
            options[token] = True
            continue
        if '=' in token:
            option, item = token.split('=', 1)
        elif token in finite and tail:
            option, item, tail = token, tail[0], tail[1:]
        else:
            result['unrecognized_or_duplicate_argument'] = True
            return result
        if option not in finite or option in options or item not in finite[option]:
            result['unrecognized_or_duplicate_argument'] = True
            return result
        options[option] = item
    if any(left in options and right in options for left, right in (
            ('--access-log', '--no-access-log'), ('--proxy-headers', '--no-proxy-headers'),
            ('--server-header', '--no-server-header'))):
        result['unrecognized_or_duplicate_argument'] = True
        return result
    result.update(status='allowlisted_invocation_observed', options=options)
    effective_directory = options.get('--app-dir', working_directory)
    bound = options.get('--factory') is True and options.get('--host') == '127.0.0.1' \
        and options.get('--workers') == '1' and options.get('--lifespan', 'auto') != 'off'
    owner_source = ((module == 'owner_app:create_app' and effective_directory == '/opt/analyst-ai/backend')
                    or (module == 'backend.owner_app:create_app' and effective_directory == '/opt/analyst-ai'))
    update_source = module == 'backend.public_updates_app:create_app' and effective_directory == '/opt/analyst-ai-updates'
    if service == SERVICES[0] and bound and owner_source and options.get('--port') == '8080':
        result.update(owner_factory_binding_verified=True, source_path='/opt/analyst-ai/backend/owner_app.py')
    if service == SERVICES[1] and bound and update_source and options.get('--port') == '8081':
        result.update(public_update_factory_binding_verified=True,
                      source_path='/opt/analyst-ai-updates/backend/public_updates_app.py')
    return result


def service_observation(name):
    try:
        values = bounded_systemctl(name)
        working = values['WorkingDirectory'] if values['WorkingDirectory'] in WORKDIRS else None
        fragment = '/etc/systemd/system/' + name
        result = {
            'status': 'observed', 'working_directory': working,
            'working_directory_allowlisted': working is not None,
            'expected_fragment_path': values['FragmentPath'] == fragment,
            'effective_dropins_present': bool(values['DropInPaths']),
            'load_state': values['LoadState'] if values['LoadState'] in {'loaded', 'not-found', 'error', 'masked'} else 'unknown',
            'active_state': values['ActiveState'] if values['ActiveState'] in {'active', 'inactive', 'failed', 'activating', 'deactivating'} else 'unknown',
            'need_daemon_reload': values['NeedDaemonReload'] if values['NeedDaemonReload'] in {'yes', 'no'} else 'unknown',
            'invocation': invocation(values['ExecStart'], working, name),
        }
        metadata, _ = observed_file(Path(fragment), 128 * 1024)
        result['unit_file_identity'] = metadata
        result['matches_prior_unit_identity'] = {k: metadata.get(k) for k in ('bytes', 'sha256')} == EXPECTED['units'][fragment]
        return result
    except (ObservationError, OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'bounded_effective_service_observation_unavailable'}

"""Finite public checks. Bodies stay in memory; no login transaction is created."""
import hashlib
from html.parser import HTMLParser
import http.client
import json
import socket
import ssl

PUBLIC_HOST = 'analyst-ai-2941515.twc1.net'
PUBLIC_IP = '83.217.195.29'
CALLBACK = '/auth/telegram/callback?error=theme_verification'
POLICY = '/client/update-policy?package_name=ru.omnicio.app.debug'
RETIRED = '/auth/telegram/owner-enrollment/callback'
CALLBACK_HEADERS = {
    # The active Caddy route adds no-store to the application's private header.
    # Observed by the read-only workflow40380214063 before any deployment.
    'cache-control': 'no-store, no-store, private',
    'referrer-policy': 'no-referrer',
    'x-content-type-options': 'nosniff',
    'content-security-policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'",
}


class PinnedRuntimeTLS(http.client.HTTPSConnection):
    def __init__(self):
        super().__init__(PUBLIC_HOST, timeout=8, context=ssl.create_default_context())

    def connect(self):
        raw = socket.create_connection((PUBLIC_IP, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=PUBLIC_HOST)
        except BaseException:
            raw.close()
            raise


class CallbackPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.styles = []
        self.links = []
        self.color_scheme = []
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, pairs):
        values = dict(pairs)
        if tag == 'style':
            self.styles.append('')
            self.current = 'style'
        elif tag == 'script':
            self.scripts.append('')
            self.current = 'script'
        elif tag == 'a':
            self.links.append(values.get('href'))
        elif tag == 'meta' and values.get('name') == 'color-scheme':
            self.color_scheme.append(values.get('content'))

    def handle_endtag(self, tag):
        if tag == self.current:
            self.current = None

    def handle_data(self, data):
        if self.current == 'style':
            self.styles[-1] += data
        elif self.current == 'script':
            self.scripts[-1] += data


def public_read(path, maximum):
    need(path in {'/health', CALLBACK, POLICY, RETIRED}, 'public_path_not_allowlisted')
    connection = PinnedRuntimeTLS()
    try:
        connection.request('GET', path, headers={'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        raw = response.read(maximum + 1)
        need(len(raw) <= maximum and response.getheader('Content-Encoding', 'identity') == 'identity',
             'public_body_outside_bound')
        headers = {key: response.getheader(key) for key in (*CALLBACK_HEADERS, 'content-type')}
        return response.status, headers, raw
    finally:
        connection.close()


def public_check(*, expected_style=None, expected_policy=None):
    status, headers, raw = public_read('/health', 1024)
    need(status == 200 and (headers['content-type'] or '').split(';')[0] == 'application/json'
         and json.loads(raw) == {'status': 'ok'}, 'public_owner_health_failed')
    status, headers, raw = public_read(CALLBACK, 65536)
    need(status == 200 and (headers['content-type'] or '').split(';')[0] == 'text/html'
         and all(headers[key] == value for key, value in CALLBACK_HEADERS.items()), 'public_callback_headers_changed')
    page = CallbackPage()
    page.feed(raw.decode('utf-8'))
    page.close()
    need(page.links == ['analystai://auth?error=telegram_denied'] and
         page.scripts == ['window.location.replace("analystai://auth?error=telegram_denied");'] and
         len(page.styles) == 1, 'public_callback_handoff_changed')
    style_sha = hashlib.sha256(page.styles[0].encode('utf-8')).hexdigest()
    if expected_style is not None:
        need(style_sha == expected_style and page.color_scheme == ['dark'],
             'public_callback_theme_bytes_differ')
    status, headers, raw = public_read(RETIRED, 4096)
    need(status == 410, 'retired_enrollment_route_changed')
    status, headers, raw = public_read(POLICY, 16384)
    need(status == 200 and (headers['content-type'] or '').split(';')[0] == 'application/json', 'public_update_policy_unavailable')
    policy = json.loads(raw)
    need(type(policy) is dict and policy.get('package_name') == 'ru.omnicio.app.debug'
         and type(policy.get('version_code')) is int and policy['version_code'] >= 44,
         'unexpected_public_update_policy')
    policy_sha = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if expected_policy is not None:
        need(policy_sha == expected_policy, 'public_update_policy_changed_during_web_deployment')
    return {'health_http': 200, 'health_body': {'status': 'ok'}, 'callback_http': 200,
            'callback_headers_verified': True, 'callback_handoff_verified': True,
            'callback_style_sha256': style_sha, 'callback_theme_verified': expected_style is not None,
            'retired_enrollment_http': 410, 'update_policy_sha256': policy_sha,
            'update_version_code': policy['version_code'], 'login_start_requested': False,
            'login_transaction_created_by_verifier': False, 'owner_denial_requested': False,
            'browser_pixels_verified': False}



def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('ascii')


def parsed(raw):
    value = json.loads(raw, object_pairs_hook=unique)
    need(type(value) is dict, 'unexpected_json_root')
    return value


def safe_relative(name):
    need(type(name) is str and 0 < len(name) <= 1024 and '\\' not in name and ':' not in name
         and '\0' not in name and '\n' not in name and '\r' not in name, 'unsafe_archive_member')
    relative = PurePosixPath(name)
    need(not relative.is_absolute() and relative.as_posix() == name and
         not any(part in ('.', '..') for part in relative.parts), 'unsafe_archive_member')


def inventory_checked(raw):
    value = parsed(raw)
    need(set(value) == {'files', 'source_sha256', 'complete_source_sha256'} and
         1 <= len(value['files']) <= 20000, 'wrong_source_inventory')
    code, complete, seen = hashlib.sha256(), hashlib.sha256(), set()
    for name, item in sorted(value['files'].items(), key=lambda row: row[0].encode('utf-8')):
        safe_relative(name)
        need(name.casefold() not in seen and set(item) == {'bytes', 'sha256'}
             and type(item['bytes']) is int and 0 <= item['bytes'] <= 128 * 1024**2
             and re.fullmatch('[a-f0-9]{64}', item['sha256']), 'invalid_source_inventory_identity')
        seen.add(name.casefold())
        record = name.encode('utf-8') + b'\0' + item['sha256'].encode('ascii') + b'\0'
        complete.update(record)
        if name not in ('AGENTS.md', 'README.md') and not name.startswith('docs/'):
            code.update(record)
    need(value['source_sha256'] == EXPECTED['source_sha256'] == code.hexdigest() and
         value['complete_source_sha256'] == EXPECTED['complete_source_sha256'] == complete.hexdigest(),
         'build_inventory_digest_changed')
    return value


def archive_inputs():
    archive = Path(EXPECTED['archive_path'])
    special = Path('/var/lib/analyst-ai-build')
    for parent in reversed(archive.parents):
        info = parent.lstat()
        owners = {0, pwd.getpwnam('analyst-build').pw_uid} if parent == special else {0}
        need(stat.S_ISDIR(info.st_mode) and parent.resolve(strict=True) == parent and
             info.st_uid in owners and not info.st_mode & 0o022, 'untrusted_build_archive_parent')
    before = archive.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1 and
         not before.st_mode & 0o022 and before.st_size == EXPECTED['archive']['bytes'], 'wrong_build_archive_file')
    with os.fdopen(os.open(archive, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        need(stable(os.fstat(stream.fileno())) == stable(before), 'build_archive_replaced')
        digest_value, count = hashlib.sha256(), 0
        for block in iter(lambda: stream.read(1024**2), b''):
            count += len(block)
            need(count <= EXPECTED['archive']['bytes'], 'build_archive_grew')
            digest_value.update(block)
        need(count == before.st_size and digest_value.hexdigest() == EXPECTED['archive']['sha256'],
             'full_build_archive_digest_changed')
        stream.seek(0)
        with zipfile.ZipFile(stream) as bundle:
            entries = bundle.infolist()
            names = [entry.filename for entry in entries]
            need(len(entries) <= 20000 and len(names) == len(set(names)) and
                 sum(entry.file_size for entry in entries) <= 490 * 1024**2, 'invalid_build_archive_inventory')
            for entry in entries:
                safe_relative(entry.filename)
                need(not entry.is_dir() and not entry.flag_bits & 1 and
                     stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG), 'unsafe_build_archive_type')

            def member(name, limit, files=None):
                row = bundle.getinfo(name)
                need(row.file_size <= limit, 'selected_archive_member_too_large')
                with bundle.open(row) as source:
                    raw = source.read(limit + 1)
                need(len(raw) == row.file_size <= limit, 'archive_member_truncated')
                if files is not None:
                    need(files[name] == identity(raw), 'archive_member_envelope_mismatch')
                return raw

            envelope = parsed(member('windows-development-envelope.json', 8 * 1024**2))
            need(envelope['schema'] == 1 and envelope['kind'] == 'windows_check_build_source_archive' and
                 envelope['base_commit'] == EXPECTED['base_commit'] and
                 envelope['source_sha256'] == EXPECTED['source_sha256'] and
                 envelope['complete_source_sha256'] == EXPECTED['complete_source_sha256'] and
                 all(envelope[key] is False for key in ('runtime_pass', 'publication_authorized', 'phone_verified')),
                 'wrong_build_archive_envelope')
            files = envelope['files']
            need(set(files) == set(names) - {'windows-development-envelope.json'} and
                 len(files) == EXPECTED['archive_files'], 'build_envelope_inventory_changed')
            for name, item in files.items():
                need(set(item) == {'bytes', 'sha256'} and item['bytes'] == bundle.getinfo(name).file_size and
                     re.fullmatch('[a-f0-9]{64}', item['sha256']), 'invalid_build_envelope_identity')
            actual = {}
            for key, name in (('build_report', 'windows-development.json'), ('build_controller', 'controller.json'),
                              ('source_inventory', 'source-final.json')):
                raw = member('evidence/' + name, 8 * 1024**2, files)
                need(identity(raw) == EXPECTED[key], 'wrong_original_build_evidence')
                actual[key] = parsed(raw)
            need(actual['build_report'] == envelope['report'] and actual['build_controller'] == envelope['controller'],
                 'archive_envelope_report_conflict')
            report = actual['build_report']
            need(report['status'] == 'passed_check_and_build_only' and report['github'] == EXPECTED['github'] and
                 report['source_sha256'] == report['source_sha256_after'] == EXPECTED['source_sha256'],
                 'archive_build_identity_or_status_changed')
            inventory = inventory_checked(member('evidence/source-final.json', 8 * 1024**2, files))
            need({'source/' + name: value for name, value in inventory['files'].items()} ==
                 {name: value for name, value in files.items() if name.startswith('source/')},
                 'archive_source_inventory_disagrees')
            linux = parsed(member('evidence/linux-linux-test-report.json', 2 * 1024**2, files))
            need(linux['source_sha256'] == EXPECTED['source_sha256'] and linux['status'] == 'passed' and
                 linux['changed_sources'] == [] and linux['platform'] == 'linux' and
                 {'compile-backend', 'backend-full-suite', 'health-openapi'} <= {row['name'] for row in linux['steps']} and
                 all(type(row['exit_code']) is int and row['exit_code'] == 0 for row in linux['steps']),
                 'real_backend_test_run_not_passed')
            junit_raw = member('evidence/linux-backend-tests.xml', 32 * 1024**2, files)
            need(b'<!DOCTYPE' not in junit_raw.upper() and b'<!ENTITY' not in junit_raw.upper(), 'junit_declarations_not_allowed')
            tree = ET.fromstring(junit_raw)
            need(tree.tag in ('testsuite', 'testsuites') and not tree.findall('.//failure') and not tree.findall('.//error'),
                 'archived_backend_tests_failed')
            suites = list(tree.iter('testsuite'))
            need(suites and all(int(suite.get('errors', '-1')) == int(suite.get('failures', '-1')) == 0 and
                 int(suite.get('tests', '0')) > 0 for suite in suites), 'archived_backend_junit_counters_failed')
            contract_count = 0
            for name, contract in EXPECTED['calendar_contracts'].items():
                module = name.removesuffix('.py')
                cases = [case for case in tree.iter('testcase') if case.get('classname') in {
                    'backend.tests.' + module, module}]
                need(len(cases) == contract['count'] and
                     {case.get('name').split('[', 1)[0] for case in cases} == set(contract['names']) and
                     all(case.find('skipped') is None for case in cases), 'actual_calendar_contract_tests_missing_or_skipped')
                test_raw = member('source/backend/tests/' + name, 2 * 1024**2, files)
                need(identity(test_raw) == contract['source'], 'tested_calendar_contract_source_changed')
                contract_count += len(cases)
            need(contract_count == EXPECTED['calendar_test_count'], 'calendar_contract_count_changed')
            desired = {}
            for name, row in EXPECTED['runtime_sources'].items():
                raw = member('source/backend/' + name, 2 * 1024**2, files)
                need(identity(raw) == row['new'], 'tested_mandate_source_changed')
                desired[name] = raw
        need(stable(os.fstat(stream.fileno())) == stable(before) == stable(archive.lstat()),
             'build_archive_changed_during_read')
    return desired, {'original_calendar_test_count': contract_count, 'original_backend_junit': identity(junit_raw),
                     'original_linux_report': files['evidence/linux-linux-test-report.json']}


def trusted_directory(path, create=False):
    if create and not path.exists():
        os.mkdir(path, 0o700)
    for item in (path, *path.parents):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode) and item.resolve(strict=True) == item and info.st_uid == 0 and
             not info.st_mode & 0o022, 'untrusted_deployment_directory')
    if path == STORE or STORE in path.parents:
        need(not path.stat().st_mode & 0o077, 'deployment_backup_directory_must_be_root_only')
    return path.stat()


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_file(path, raw, metadata=None):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        if metadata is not None:
            os.fchown(stream.fileno(), metadata['uid'], metadata['gid'])
            os.fchmod(stream.fileno(), metadata['mode'])
        os.fsync(stream.fileno())
    need(identity(trusted_read(path, 2 * 1024**2)) == identity(raw), 'staged_file_readback_failed')


def write_journal(folder, value):
    temporary = folder / ('journal-' + uuid.uuid4().hex + '.tmp')
    create_file(temporary, encoded(value))
    os.replace(temporary, folder / 'journal.json')
    sync_directory(folder)


def current_source(name):
    need(name in EXPECTED['runtime_sources'] and Path(name).name == name, 'unexpected_source_name')
    trusted_directory(SOURCE_ROOT)
    path = SOURCE_ROOT / name
    try:
        path.lstat()
    except FileNotFoundError:
        need(EXPECTED['runtime_sources'][name]['old'] is None, 'existing_runtime_source_disappeared')
        return None
    return identity(trusted_read(path, 2 * 1024**2))


def source_identities():
    return {name: current_source(name) for name in EXPECTED['runtime_sources']}


def service_binding(service, *, required_active):
    observed = service_observation(service)
    expected = dict(EXPECTED['services'][service])
    if not required_active:
        need(observed.get('active_state') in {'active', 'inactive', 'failed', 'activating', 'deactivating'},
             'owner_service_state_unknown')
        expected['active_state'] = observed['active_state']
    need(observed == expected, 'effective_service_binding_changed')


def safeguards(*, owner_active):
    for name, expected in EXPECTED['untouched_sources'].items():
        need(identity(trusted_read(Path(name), 2 * 1024**2)) == expected, 'unrelated_runtime_source_changed')
    need(identity(trusted_read(Path('/etc/caddy/Caddyfile'), 128 * 1024)) == EXPECTED['caddy_file'],
         'caddy_file_changed')
    metadata, _ = active_caddy()
    need(metadata == {'status': 'observed', **EXPECTED['active_caddy']}, 'active_caddy_changed')
    for service in SERVICES:
        service_binding(service, required_active=(service != SERVICES[0] or owner_active))


def service_pid(name):
    need(name in SERVICES, 'unexpected_service_pid')
    result = subprocess.run(['systemctl', 'show', name, '--property=MainPID', '--value'], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
    need(result.returncode == 0 and len(result.stdout) <= 32 and re.fullmatch(rb'[0-9]+\n?', result.stdout),
         'service_pid_unavailable')
    return int(result.stdout)


def owner_action(action):
    need(action in {'stop', 'start'}, 'owner_action_not_allowlisted')
    result = subprocess.run(['systemctl', action, SERVICES[0]], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45, check=False)
    need(result.returncode == 0, 'owner_' + action + '_failed')
    if action == 'stop':
        need(service_pid(SERVICES[0]) == 0, 'owner_did_not_stop')


def local_health():
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=2)
        try:
            connection.request('GET', '/health')
            response = connection.getresponse()
            raw = response.read(1025)
            if response.status == 200 and len(raw) <= 1024 and json.loads(raw) == {'status': 'ok'}:
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(0.5)
    raise ObservationError('local_owner_health_failed')


def replace_sources(folder, sources, metadata):
    need(folder.stat().st_dev == SOURCE_ROOT.stat().st_dev, 'stage_not_on_source_filesystem')
    staged = {}
    for name, raw in sources.items():
        if raw is None:
            need(EXPECTED['runtime_sources'][name]['old'] is None, 'only_owned_new_module_can_be_removed')
            staged[name] = None
            continue
        path = folder / ('stage-' + uuid.uuid4().hex + '-' + name)
        create_file(path, raw, metadata[name])
        staged[name] = path
    for name, path in staged.items():
        current = current_source(name)
        need(current in (EXPECTED['runtime_sources'][name]['old'], EXPECTED['runtime_sources'][name]['new']),
             'source_replacement_would_overwrite_unrelated_bytes')
        if path is None:
            if current is not None:
                need(current == EXPECTED['runtime_sources'][name]['new'], 'new_module_changed_before_removal')
                os.unlink(SOURCE_ROOT / name)
        else:
            os.replace(path, SOURCE_ROOT / name)
        sync_directory(SOURCE_ROOT)
    need(source_identities() == {name: identity(raw) if raw is not None else None for name, raw in sources.items()},
         'replaced_source_readback_failed')
    for name, old in metadata.items():
        if sources[name] is None:
            continue
        info = (SOURCE_ROOT / name).lstat()
        need({'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode)} == old,
             'source_ownership_or_mode_changed')


def rollback(folder, journal):
    old = {name: trusted_read(folder / ('original-' + name), 2 * 1024**2) if row['old'] is not None else None
           for name, row in EXPECTED['runtime_sources'].items()}
    need(all((identity(raw) if raw is not None else None) == EXPECTED['runtime_sources'][name]['old'] for name, raw in old.items()),
         'rollback_bytes_not_original_runtime')
    current = source_identities()
    need(all(current[name] in (row['old'], row['new']) for name, row in EXPECTED['runtime_sources'].items()),
         'rollback_would_overwrite_unrelated_source')
    # A Caddy outage or update-service verification failure must not suppress
    # restoration of this transaction's original source bytes. Only the exact
    # owner unit/invocation and owned file identities gate the restore itself.
    service_binding(SERVICES[0], required_active=False)
    owner_action('stop')
    replace_sources(folder, old, journal['metadata'])
    owner_action('start')
    local_health()
    service_binding(SERVICES[0], required_active=True)
    public_verified = False
    try:
        public_check(expected_policy=journal['original_policy_sha256'])
        public_verified = True
    except (ObservationError, OSError, ValueError, http.client.HTTPException):
        pass
    journal.update(phase='rolled_back', rollback_succeeded=True, rollback_public_verified=public_verified,
                   completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write_journal(folder, journal)
    return public_verified


def deploy_locked(folder, desired, build_evidence):
    expected_old = {name: row['old'] for name, row in EXPECTED['runtime_sources'].items()}
    expected_new = {name: row['new'] for name, row in EXPECTED['runtime_sources'].items()}
    binding = {key: EXPECTED[key] for key in ('source_sha256', 'source_backup_commit', 'archive', 'build_report')}
    journal_path = folder / 'journal.json'
    if journal_path.exists():
        journal = parsed(trusted_read(journal_path, 65536))
        need(journal['schema'] == 1 and journal['binding'] == binding and
             set(journal['metadata']) == set(expected_old), 'foreign_or_invalid_deployment_journal')
        for metadata in journal['metadata'].values():
            need(set(metadata) == {'uid', 'gid', 'mode'} and metadata['uid'] == 0 and
                 type(metadata['gid']) is int and metadata['gid'] >= 0 and
                 metadata['mode'] in (0o644, 0o640), 'invalid_original_source_metadata')
        if journal['phase'] == 'committed':
            need(source_identities() == expected_new, 'committed_mandate_source_changed')
            safeguards(owner_active=True)
            public = public_check(expected_style=EXPECTED['callback_style_sha256'])
            return receipt('already_deployed_verified', build_evidence, public, True)
        need(journal['phase'] in {'prepared', 'installing', 'verifying', 'rolled_back', 'rollback_failed'},
             'unknown_deployment_phase')
        # A retry resumes only this exact transaction. Never accept a random
        # mixed source tree as a usable starting state.
        if journal['phase'] != 'rolled_back':
            # Recovery is already a restoration path. Keep it protected against
            # a second interrupt just like the ordinary failure restoration.
            for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                signal.signal(signum, signal.SIG_IGN)
            try:
                rollback(folder, journal)
            finally:
                for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                    signal.signal(signum, interrupted)
        need(source_identities() == expected_old, 'rollback_did_not_restore_old_source')
    else:
        need(source_identities() == expected_old, 'current_runtime_not_exact_observed_baseline')
        safeguards(owner_active=True)
        previous = public_check()
        metadata = {}
        for name, item in expected_old.items():
            path = SOURCE_ROOT / name
            if item is None:
                need(name in ('market_schedule.py', 'background_dispatch.py', 'event_monitor.py') and current_source(name) is None, 'new_module_present_before_install')
                metadata[name] = {'uid': 0, 'gid': 0, 'mode': 0o644}
                continue
            raw = trusted_read(path, 2 * 1024**2)
            need(identity(raw) == item, 'source_changed_before_backup')
            info = path.lstat()
            need(info.st_uid == 0 and stat.S_IMODE(info.st_mode) in (0o644, 0o640),
                 'runtime_source_metadata_not_expected')
            metadata[name] = {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode)}
            backup = folder / ('original-' + name)
            if backup.exists():
                need(identity(trusted_read(backup, 2 * 1024**2)) == item, 'partial_backup_differs')
            else:
                create_file(backup, raw)
        journal = {'schema': 1, 'binding': binding, 'metadata': metadata, 'phase': 'prepared',
                   'original_policy_sha256': previous['update_policy_sha256'], 'rollback_succeeded': False}
        write_journal(folder, journal)
    safeguards(owner_active=True)
    public_check(expected_policy=journal['original_policy_sha256'])
    updates_pid = service_pid(SERVICES[1])
    need(updates_pid > 0, 'update_service_not_running')
    try:
        journal.update(phase='installing', rollback_succeeded=False)
        write_journal(folder, journal)
        owner_action('stop')
        need(source_identities() == expected_old, 'old_source_changed_after_stop')
        replace_sources(folder, desired, journal['metadata'])
        journal['phase'] = 'verifying'
        write_journal(folder, journal)
        owner_action('start')
        local_health()
        safeguards(owner_active=True)
        need(service_pid(SERVICES[1]) == updates_pid, 'update_service_changed_during_deployment')
        public = public_check(expected_style=EXPECTED['callback_style_sha256'],
                              expected_policy=journal['original_policy_sha256'])
        journal.update(phase='committed', completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write_journal(folder, journal)
        return receipt('deployed_verified', build_evidence, public, False)
    except BaseException:
        # Do not permit a second interrupt to truncate the owned restoration.
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, signal.SIG_IGN)
        try:
            public_verified = rollback(folder, journal)
        except BaseException:
            journal['phase'] = 'rollback_failed'
            try:
                write_journal(folder, journal)
            except BaseException:
                pass
            raise ObservationError('deployment_failed_rollback_requires_review') from None
        code = ('deployment_failed_original_sources_restored' if public_verified else
                'deployment_failed_original_sources_restored_public_unverified')
        raise ObservationError(code) from None


def receipt(status, evidence, public, idempotent):
    return {'schema': 1, 'kind': 'calendar49_exact_nine_file_deployment', 'status': status,
            'runtime_server_id': 9417611, 'public_host': PUBLIC_HOST,
            'source_sha256': EXPECTED['source_sha256'], 'source_backup_commit': EXPECTED['source_backup_commit'],
            'archive': EXPECTED['archive'], 'build_report': EXPECTED['build_report'],
            'runtime_sources': {name: row['new'] for name, row in EXPECTED['runtime_sources'].items()},
            'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'full_windows_check_and_build_passed': True, 'actual_calendar_test_evidence': evidence,
            'public': public, 'idempotent_verification': idempotent,
            'owner_service_restart_performed': not idempotent,
            'other_services_restarted_by_deployer': False, 'caddy_or_service_configuration_changed': False,
            'database_or_environment_files_opened_by_deployer': False,
            'normal_owner_startup_has_possible_database_effects': True,
            'help_deployed': False, 'dependencies_changed': False, 'apk_published_or_installed': False,
            'trading_or_model_routes_called': False, 'physical_phone_verified': False,
            'full_android_runtime_matrix_passed': False}


def main():
    need(__debug__ and sys.platform == 'linux' and os.geteuid() == 0, 'pinned_linux_root_transport_required')
    need(set(EXPECTED['runtime_sources']) == set(('autonomous_ai.py', 'autonomous_controller.py', 'volume_jobs.py', 'volume_workspace.py', 'volume_monitor.py', 'volume_market.py', 'market_schedule.py', 'background_dispatch.py', 'event_monitor.py')), 'deployment_scope_changed')
    desired, evidence = archive_inputs()
    trusted_directory(SOURCE_ROOT)
    trusted_directory(STORE, create=True)
    lock_path = STORE / 'deployment.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+b') as lock:
        info = os.fstat(lock.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
             not info.st_mode & 0o077 and stable(info) == stable(lock_path.lstat()), 'unsafe_deployment_lock')
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = STORE / EXPECTED['source_sha256']
        trusted_directory(folder, create=True)
        result = deploy_locked(folder, desired, evidence)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)


def interrupted(signum, frame):
    raise ObservationError('administrative_transport_interrupted')


if __name__ == '__main__':
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, interrupted)
    try:
        main()
    except BaseException as error:
        # No traceback, subprocess text, config, file body, credentials or URL
        # parameters may escape. ObservationError messages are finite literals.
        code = str(error) if isinstance(error, ObservationError) else 'bounded_mandate_deployment_failed'
        print(json.dumps({'schema': 1, 'kind': 'calendar49_deployment_failure', 'code': code}), flush=True)
        # Return the bounded failure JSON through the existing capture transport.
        # The hosted receiver persists it and requires a successful receipt; it
        # explicitly fails the workflow for this kind. No success is inferred
        # from the transport exit status.
