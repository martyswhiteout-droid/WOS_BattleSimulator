"""Predictor app layer — turns config profiles into engine input (Layer 1),
runs the Monte-Carlo, and summarises results for the UI (Layer 2).

Codes against the engine (wos_sim.pvp_engine) through a swappable kernel seam,
so the real stochastic engine drops in with no changes to this layer.
"""
