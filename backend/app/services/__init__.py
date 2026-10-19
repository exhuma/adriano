"""
Business services (orchestration over the domain, ports and storage).

Services depend only on :mod:`app.domain`, the storage port
(:mod:`app.storage.port`) and the source port (:mod:`app.sources.port`);
concrete implementations are injected by the composition root
(:mod:`app.composition`).
"""
