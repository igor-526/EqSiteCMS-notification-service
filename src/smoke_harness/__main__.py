import asyncio
import os
import sys

from smoke_harness.config import HarnessConfig, HarnessConfigurationError
from smoke_harness.runner import HarnessExecutionError, HarnessResult, run_harness


async def _cleanup_owned_by_smoke_orchestrator(config: HarnessConfig) -> None:
    # The harness creates no fixtures. The smoke skill owns and removes the exact IDs supplied in config.
    del config


async def _main() -> int:
    try:
        config = HarnessConfig.from_environment(dict(os.environ))
    except HarnessConfigurationError as exc:
        print(f"notification smoke harness rejected: {exc}", file=sys.stderr)
        return 2

    # Importing the real composition root is deliberately after the fail-fast guard.
    from smoke_harness.composition import build_production_dependencies

    try:
        result = await run_harness(
            config=config,
            dependency_factory=build_production_dependencies,
            cleanup=_cleanup_owned_by_smoke_orchestrator,
        )
    except HarnessExecutionError as exc:
        _print_result(exc.result)
        return 1
    except Exception:
        print("notification smoke harness failed", file=sys.stderr)
        return 1
    _print_result(result)
    return 0


def _print_result(result: HarnessResult) -> None:
    print(
        "notification smoke harness completed "
        f"email_attempts={result.email.attempts} email_recipients={result.email.recipient_count} "
        f"vk_attempts={result.vk.attempts} vk_recipients={result.vk.recipient_count} "
        f"email_aliases={','.join(result.email.recipient_aliases) or 'none'} "
        f"vk_aliases={','.join(result.vk.recipient_aliases) or 'none'} "
        f"superuser_aliases={','.join(result.superuser_aliases) or 'none'} "
        f"vk_contract_valid={str(result.vk.contract_valid).lower()} "
        f"vk_text_fields={str(result.vk.text_fields_present).lower()} "
        f"vk_text_fallback={str(result.vk.text_uses_fallback).lower()} "
        f"vk_text_internal_uuid={str(result.vk.text_has_internal_uuid).lower()}"
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
