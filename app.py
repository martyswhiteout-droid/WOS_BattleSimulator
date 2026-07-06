"""Vercel FastAPI entrypoint.

Vercel discovers a top-level FastAPI instance named `app` from supported
entrypoints. The real app lives in the predictor package so local uvicorn usage
continues to work unchanged.
"""
from wos_sim.predictor.server import app

