# Canonical content hashing (`sha256-v1`)

Audience: developers and architects who need to reproduce or reason
about the digest that approval evidence is bound to. See
`docs/approval.md` for how the digest is used, and
`backend/app/domain/hashing.py` for the reference implementation.

## Algorithm

Digest string format: `sha256-v1:<64 lowercase hex characters>`.

Given the exact bytes fetched or pushed:

1. Decode as strict UTF-8. If this fails, stop here (see "Bytes that
   are not valid UTF-8" below).
2. Remove exactly one leading U+FEFF byte-order mark, if present.
3. Replace every `CRLF` with `LF`, then replace any remaining lone
   `CR` with `LF`.
4. Encode the result as UTF-8 and compute its SHA-256 digest.

The digest covers the **complete file**: YAML frontmatter and the
Markdown body together, exactly as indexed. Nothing else enters the
hash: no path, branch/ref, commit id, project, or source registration
id. This is deliberate -- see "What is excluded" below.

## Test vectors

Computed from the files actually bundled in this repository, using
the backend's own `content_digest()`
(`backend/app/domain/hashing.py`); reproduce them with
`python3 -c "import hashlib; ..."` following the four steps above, or
by polling the demo stack and reading the digest back from
`GET /api/v1/records/{id}`.

1. **`samples/adr-root/platform/doc/decisions/2024-01-10-use-postgresql.md`**
   (legacy record, as committed, LF line endings):

   ```text
   sha256-v1:ffb54010060b598206bf9317aad5af478c99c429ba8ffc81c3354acbae0b2a70
   ```

   The same file with every `\n` replaced by `\r\n` (CRLF), and again
   with a leading UTF-8 BOM added on top of that, **both produce the
   identical digest above** -- demonstrating steps 2 and 3 of the
   algorithm (acceptance criterion 17: the digest is reproducible
   across encodings of the same canonical content).

2. **`samples/candidates/2026-01-05-use-redis-for-caching.md`**, as
   pushed by `samples/push-candidate.sh` in the demo (candidate
   content, unchanged from the file on disk):

   ```text
   sha256-v1:a0b7e2410924a9e396c91a984174f497cdcacdbfc5625ca5cd24679e1cb82c28
   ```

   When this exact file is later copied byte-for-byte into
   `samples/adr-root/platform/doc/decisions/` and polled, the
   published row gets this **same digest** and is promoted to
   "Accepted -- published" without losing the candidate's acceptance
   history (acceptance criterion 13; see `docs/approval.md`
   "Promotion").

3. **`samples/candidates/2026-01-10-adopt-kafka-for-events.md`**, as
   pushed (a second, independent content revision):

   ```text
   sha256-v1:45d5d718b2f019362ea6d0282c0a7ba79fae7d89fbb6aaacf27b03df31f2da5c
   ```

## What is excluded

Branch names, commit identifiers, source registration ids, and source
paths are deliberately **not** part of the input. Consequences:

- Identical canonical content submitted from a feature branch and
  later found on the published/default ref produces the same digest
  and keeps its approval/acceptance evidence (promotion, acceptance
  criterion 13).
- Moving a file to a different path, or committing the same bytes in
  a different commit, never changes its digest.
- Any content edit -- even a single character -- produces a different
  digest, so a prior approval does not silently carry over to the new
  revision (acceptance criterion 18); the old revision's history is
  retained separately (see `revision` and `decision_event` in
  `phases/DECISIONS.md` "Persistence").

## Bytes that are not valid UTF-8

A file is still stored even when it cannot be decoded as UTF-8: its
digest is computed directly over the raw bytes under the separate
algorithm label `sha256-raw-v1:<hex>` (no canonicalization is
possible), the issue `bad_encoding` is reported, and the record
**cannot be approved** until it is re-saved as UTF-8. Every other
record stays fully browseable and approvable.

## Limits (what the digest does not prove)

The digest identifies a **content revision** -- nothing more:

- **No authorship proof.** It does not prove who wrote the content,
  only that this exact byte sequence (after canonicalization) was
  indexed. Authorship, where known (CI push `author`, GitLab commit
  author), is stored separately and is not cryptographically bound to
  the content.
- **No publication proof.** It does not prove the content was ever
  published, reviewed in a pull request, or merged anywhere; it is
  computed identically for a candidate on a feature branch and for
  the same bytes on the default branch.
- **No tamper evidence for persistence itself.** The digest is a
  property of the *document*, not of the *database rows* that record
  decisions about it. An attacker or bug with write access to the
  `decision_event`/`revision` tables could, in principle, alter
  stored history; ordinary relational persistence (even with the
  append-only trigger described in `phases/DECISIONS.md`
  "Persistence") is not a substitute for a tamper-evident log. Do not
  present acceptance history as cryptographically immutable.

## Deferred: tamper evidence for the audit trail

If tamper evidence for the approval history itself is required in a
later iteration, the proposed, separately scoped control is a
**signed periodic audit export**: a batch job that selects new
`decision_event` rows since the last export, serializes them
deterministically, signs the result with a key held outside the
application database (e.g. an HSM-backed or offline signing key), and
publishes the signed export to protected, write-once storage (e.g. an
object store with object lock/retention). Verifiers can then confirm
that a given decision event is included in a signed export without
trusting the live database. This is explicitly **not** implemented in
Phase 1 (see `phases/DECISIONS.md` "Deferred"); do not imply that
ordinary persistence rows are cryptographically immutable in the
meantime.
