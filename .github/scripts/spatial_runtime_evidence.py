"""Bind mesh diagnostics to separately observed Android API and memory page size."""
from __future__ import annotations

from kernel_page_size import system_image


def _observed_integer(value: str) -> int:
    if not isinstance(value, str) or len(value) > 32:
        raise AssertionError('Invalid runtime measurement')
    text = value.strip()
    if not text or not text.isascii() or not text.isdecimal():
        raise AssertionError('Invalid runtime measurement')
    return int(text)


def observe_runtime(command) -> dict:
    api = _observed_integer(command('shell', 'getprop', 'ro.build.version.sdk'))
    abi = command('shell', 'getprop', 'ro.product.cpu.abi').strip()
    page_bytes = _observed_integer(command('shell', 'getconf', 'PAGE_SIZE'))
    if abi != 'x86_64':
        raise AssertionError('The mesh runtime has an unexpected ABI')
    # Both axes must belong to the current contract. Never derive page size
    # from API or use the default image for the independently measured 16KB run.
    image = system_image(api, page_bytes)
    return {'sdk': api, 'abi': abi, 'page_size_bytes': page_bytes, 'system_image': image}
