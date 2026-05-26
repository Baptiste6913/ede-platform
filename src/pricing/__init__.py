"""External pricing module (Phase 9.1c).

Provides yfinance-backed EOD close lookups with a local SQLite cache, used to
recompute mixed-offer values and to validate suspect-low parser outputs.
"""
