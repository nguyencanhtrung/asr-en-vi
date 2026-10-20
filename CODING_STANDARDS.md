# Coding standards

These rules guide reviewer judgement.

- Trace response fields that assert external effects (`revoked`, `deleted`, `persisted`, `verified`) to code that observed the effect. When a provider reuses another provider's response shape, re-check every field against its own backend.
- Keep test doubles for external binaries and services to behavior pinned by a contract test or a cited source fact.
