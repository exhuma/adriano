"""
Source adapters and their provider-neutral port.

- :mod:`app.sources.port` -- the :class:`~app.sources.port.SourceAdapter`
  protocol, its value types and the source error hierarchy.
- :mod:`app.sources.registry` -- source type -> validator/factory and the
  validation of type-specific registration settings.

Adapters are constructed only by :mod:`app.services.polling`.
"""
