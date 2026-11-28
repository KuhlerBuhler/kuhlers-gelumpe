#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Worker tests of one group against $BFIN_WORKER, by default the worker
# tools/emu/blackfin_worker.py picks (QEMU, else GNU):
#   qemu_worker_tests.sh kern|host|dma|fork|alle
# The tests skip themselves without a worker, so a skipped test fails this
# run unless tools/dsp/qemu_gnu_only.txt lists it (one test id per line, with
# the reason after a '#').
set -eu
here=$(cd "$(dirname "$0")" && pwd)
emu="$here/../emu"
group=${1:-}

python="$emu/.venv/bin/python"
[ -x "$python" ] || python=python3
BFIN_WORKER=$(cd "$emu" && "$python" -c 'import blackfin_worker; print(blackfin_worker.find() or "")')
if [ -z "$BFIN_WORKER" ] || [ ! -x "$BFIN_WORKER" ]; then
    echo "no Blackfin worker: build one (build_qemu.py or build_blackfin.py) or set BFIN_WORKER" >&2
    exit 2
fi
export BFIN_WORKER
echo "worker: $BFIN_WORKER" >&2

B=test_blackfin_backend.Execution
case "$group" in
kern)
    tests="test_blackfin_memory test_blackfin_backend.Failures
        $B.test_real_instructions_produce_memory_and_sign_extended_registers
        $B.test_parallel_arithmetic_store_reads_the_original_source_register
        $B.test_parallel_signbits_store_reads_the_original_destination_register
        $B.test_parallel_pointer_load_store_reads_the_original_register
        $B.test_parallel_negate_store_reads_the_original_register
        $B.test_run_stops_at_a_requested_pc
        $B.test_rewritten_l1_code_runs_the_new_instructions
        $B.test_queued_requests_never_reach_the_dsp_as_uart_input
        $B.test_core_timer_observes_all_modeled_instruction_cycles
        $B.test_illegal_instruction_raises_and_invalidates_the_backend
        $B.test_invalid_memory_and_oversized_requests_are_rejected
        $B.test_empty_gnu_boot_rom_is_not_mapped_as_executable_memory
        $B.test_executing_missing_rom_fails_before_a_fake_rom_instruction
        $B.test_unknown_rom_reports_the_stopped_pc_caller_and_registers
        $B.test_rom_entry_cannot_be_accepted_as_a_successful_breakpoint
        $B.test_rom_stop_identifies_the_executed_call_site
        $B.test_rom_entry_at_the_instruction_budget_is_still_a_failure" ;;
host)
    tests="test_blackfin_hostdp test_blackfin_host_fifo test_blackfin_syscontrol test_blackfin_clock
        test_blackfin_probe
        $B.test_host_port_reads_words_created_by_executed_dsp_code
        $B.test_boot_never_claims_ready_for_a_program_that_only_loops
        $B.test_short_host_transfer_invalidates_the_port
        $B.test_boot_rejects_truncated_and_corrupt_streams
        $B.test_machine_dispatch_uses_the_executed_dsp_memory_and_rejects_snapshots
        $B.test_machine_upload_passes_the_actual_cpu_stream_to_the_backend" ;;
dma)
    tests="test_blackfin_sport test_blackfin_mdma test_blackfin_stream" ;;
fork)
    tests="test_blackfin_swap
        $B.test_shared_memory_channel_carries_full_size_transfers_around_the_ring
        $B.test_a_worker_copy_goes_on_exactly_as_the_original
        $B.test_poll_ahead_matches_one_advance_per_poll
        $B.test_cases_run_from_one_state_in_process_copies" ;;
alle)
    tests="test_blackfin_backend test_blackfin_clock test_blackfin_host_fifo test_blackfin_hostdp
        test_blackfin_mdma test_blackfin_memory test_blackfin_probe test_blackfin_sport
        test_blackfin_stream test_blackfin_swap test_blackfin_syscontrol" ;;
*)
    echo "usage: $0 kern|host|dma|fork|alle" >&2
    exit 2 ;;
esac

log=$(mktemp)
trap 'rm -f "$log"' EXIT
status=0
# shellcheck disable=SC2086
(cd "$emu" && "$python" -m unittest -v $tests) >"$log" 2>&1 || status=$?
cat "$log"

allowed="$here/qemu_gnu_only.txt"
bad=$(grep -E ' \.\.\. skipped' "$log" | while read -r _ id _; do
    test_id=$(printf '%s' "$id" | tr -d '()')
    grep -q "^$test_id *#" "$allowed" 2>/dev/null || echo "$test_id"
done)
if [ -n "$bad" ]; then
    echo "skipped without an entry in qemu_gnu_only.txt:" >&2
    echo "$bad" >&2
    exit 1
fi
exit "$status"
