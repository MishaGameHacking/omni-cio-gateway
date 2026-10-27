#!/usr/bin/env python3
"""Run bounded N08 scenarios with synthetic money in a new isolated directory.

No broker/token/environment settings are loaded. This command cannot trade.
Usage: python tools/run_paper_execution.py --output-directory /tmp/unique-run
Do not interpret these synthetic scenarios as sandbox or owner-device evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.paper_execution import AccountSnapshot, ExecutionError, OrderIntent, PaperJournal, SimulatedScope

NANO = 1_000_000_000
SCOPE = SimulatedScope('synthetic-owner', 'synthetic-no-network-broker', 'synthetic-account')


def _expect(code, action):
    try:
        action()
    except ExecutionError as error:
        if str(error) != code:
            raise
        return
    raise RuntimeError('expected_safety_refusal_missing_' + code)


def run(directory: Path) -> dict:
    directory = directory.absolute()
    # No overwrite, no existing database, no implicit default production path.
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    receipts = []
    for scenario in ('timeout_restart', 'partial_cancel', 'manual_change'):
        clock = [1000]
        path = directory / (scenario + '.paper.sqlite3')
        journal = PaperJournal(path, SCOPE, clock=lambda: clock[0])
        before = AccountSnapshot(SCOPE, 0, 1, 999, 1000*NANO, {'synthetic-share': 100}, 'a'*64, True)
        journal.initialize_account(before)
        intent = OrderIntent(SCOPE, 'synthetic-request', 'synthetic-plan', 'b'*64, 'c'*64,
                             0, 1, 'synthetic-share', 'buy', 10, 1, 10*NANO, 2*NANO, 2000)
        order = journal.prepare(intent)
        lease = journal.claim('worker-before', seconds=1 if scenario == 'timeout_restart' else 60)
        if scenario == 'manual_change':
            after = replace(before, revision=1, observed_at=clock[0], cash_nanorub=800*NANO,
                            available_units={'synthetic-share': 120}, evidence_sha256='d'*64)
            journal.reconcile_account(after, lease, completed_order_ids=[])
            _expect('paper_send_not_repeatable', lambda: journal.begin_send(order, lease))
            expected_state, expected_lots, expected_sends = 'invalidated', 0, 0
        else:
            journal.begin_send(order, lease)
            if scenario == 'timeout_restart':
                clock[0] += 1
                journal = PaperJournal(path, SCOPE, clock=lambda: clock[0])
                lease = journal.claim('worker-after')
                _expect('paper_send_not_repeatable', lambda: journal.begin_send(order, lease))
                journal.pause(True)
                terminal, lots, value, fees = 'filled', 10, 100*NANO, NANO
            else:
                journal.observe(order, lease, observation_id='partial', sequence=1,
                                state='partial', filled_lots=4, executed_nanorub=40*NANO, fee_nanorub=400_000_000)
                journal.request_cancel(order, lease)
                terminal, lots, value, fees = 'cancelled', 6, 60*NANO, 600_000_000
            journal.observe(order, lease, observation_id='terminal', sequence=2, state=terminal,
                            filled_lots=lots, executed_nanorub=value, fee_nanorub=fees)
            held = journal.status()['reserved_nanorub']
            if held != 102*NANO:
                raise RuntimeError('reservation_released_before_independent_reconciliation')
            clock[0] += 1
            after = replace(before, revision=1, observed_at=clock[0], cash_nanorub=1000*NANO-value-fees,
                            available_units={'synthetic-share': 100+lots}, evidence_sha256='d'*64)
            journal.reconcile_account(after, lease, completed_order_ids=[order])
            expected_state, expected_lots, expected_sends = terminal, lots, 1
        status = journal.status()
        current = status['orders'][0]
        if (status['reserved_nanorub'] != 0 or current['state'] != expected_state
                or current['filled_lots'] != expected_lots or current['sends'] != expected_sends
                or not journal.verify_event_chain()):
            raise RuntimeError('paper_scenario_failed_' + scenario)
        receipts.append({'scenario': scenario, 'passed': True, 'final_state': expected_state,
                         'filled_lots': expected_lots, 'send_intents': expected_sends,
                         'event_chain_valid': True, 'database_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    report = {'schema': 1, 'mode': 'simulation', 'synthetic_data_only': True,
              'real_orders_enabled': False, 'network_transport': False,
              'sandbox_tested': False, 'owner_portfolio_used': False,
              'scenarios': receipts, 'complete': True,
              'recorded_at_utc': datetime.now(timezone.utc).isoformat()}
    (directory/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output_directory), indent=2))


if __name__ == '__main__':
    main()
