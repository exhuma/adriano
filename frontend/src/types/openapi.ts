/**
 * Generated from the backend OpenAPI schema. Do not hand-edit.
 * Regenerate with `npm run gen:types` (see scripts/gen-types.mjs).
 */

export type JsonValue = string | number | boolean | JsonValue[] | {
            [key: string]: JsonValue;
        } | null;

export interface paths {
    "/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Healthz
         * @description Report application, database and configuration health.
         *
         *     Returns HTTP 200 with ``status: ok`` when the database is
         *     reachable, or HTTP 503 with ``status: degraded`` otherwise. The
         *     ``config``, ``policy`` and ``registrations`` keys report the
         *     configuration loaded at startup.
         *
         *     :param response: Outgoing response, used to set the status code.
         *     :param db: Request-scoped database session.
         *     :param runtime: Startup state of the catalog.
         *     :param settings: Application settings (auth status).
         *     :returns: A mapping with ``status``, ``database``, ``config``,
         *         ``policy``, ``registrations``, ``rbac`` and ``auth`` keys.
         */
        get: operations["healthz_healthz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Me
         * @description Describe the caller.
         *
         *     :param principal: The authenticated caller.
         *     :param permissions: The caller's permissions.
         *     :param runtime: Startup state (approval policy).
         *     :returns: Identity, permissions and reviewer eligibility.
         */
        get: operations["get_me_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Records
         * @description Search the catalog with the Phase 1 filters.
         *
         *     :param q: Free text (titles, bodies, UUIDs, paths); blank or
         *         omitted matches everything.
         *     :param source: Restrict to one registration id.
         *     :param project: Restrict to one project path.
         *     :param state: Restrict to ``published`` or ``candidate``.
         *     :param needs_approval: Restrict to records that need approval.
         *     :param record_type: Decisions (default), errata, or both.
         *     :param page: 1-based page number.
         *     :param page_size: Page size, 1 to :data:`~app.storage.port.MAX_PAGE_SIZE`.
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state.
         *     :returns: The page.
         */
        get: operations["list_records_api_v1_records_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/records/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Record
         * @description Fetch one record's detail page.
         *
         *     ``approval.can_decide`` (and the blocked reason) is evaluated for
         *     the caller.
         *
         *     :param record_id: Record id.
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state.
         *     :param settings: Application settings (for the stale threshold).
         *     :param principal: The authenticated caller.
         *     :returns: The detail.
         *     :raises app.errors.NotFoundError: If the record does not exist.
         */
        get: operations["get_record_api_v1_records__record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/records/{record_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Record Diff
         * @description Diff two stored snapshots of the record's identity.
         *
         *     Only digests related to the record are accepted (404
         *     ``unknown_revision`` otherwise); see :mod:`app.services.diff`.
         *
         *     :param record_id: Record id.
         *     :param from_digest: Base digest (query ``from``).
         *     :param to_digest: Target digest (query ``to``).
         *     :param provider: Storage provider (overridden by tests).
         *     :returns: The diff, or ``base: null`` with ``reason:
         *         "no_prior_revision"``.
         */
        get: operations["get_record_diff_api_v1_records__record_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sources
         * @description List every stored source registration.
         *
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state.
         *     :param settings: Application settings (for the stale threshold).
         *     :returns: One entry per stored registration, ordered by id.
         */
        get: operations["list_sources_api_v1_sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources/poll": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Poll All Sources
         * @description Poll every pollable registration in the background.
         *
         *     :param background: Background task queue.
         *     :param principal: The operator (``operate`` permission).
         *     :param runtime: Startup state.
         *     :param provider: Storage provider (overridden by tests).
         *     :returns: The accepted ids (HTTP 202).
         *     :raises app.errors.ConflictError: If nothing is pollable.
         */
        post: operations["poll_all_sources_api_v1_sources_poll_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources/{source_id}/poll": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Poll One Source
         * @description Poll one registration in the background.
         *
         *     :param source_id: Registration id.
         *     :param background: Background task queue.
         *     :param principal: The operator (``operate`` permission).
         *     :param runtime: Startup state.
         *     :param provider: Storage provider (overridden by tests).
         *     :returns: The accepted id (HTTP 202).
         *     :raises app.errors.NotFoundError: If the id is not configured.
         *     :raises app.errors.ConflictError: If it cannot be polled.
         */
        post: operations["poll_one_source_api_v1_sources__source_id__poll_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/facets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Facets
         * @description List sources and their projects with record counts.
         *
         *     :param provider: Storage provider (overridden by tests).
         *     :returns: The facets.
         */
        get: operations["get_facets_api_v1_facets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/records/{record_id}/decisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Post Decision
         * @description Record an accept/reject decision for the record's current digest.
         *
         *     :param record_id: Record id.
         *     :param body: Action, optional comment and expected digest.
         *     :param principal: The authenticated caller (``read`` required).
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state (approval policy).
         *     :returns: The stored event.
         */
        post: operations["post_decision_api_v1_records__record_id__decisions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Put Candidate
         * @description Create or replace the candidate for (source, project, ADR, ref).
         *
         *     :param request: The request.
         *     :param response: The response.
         *     :param credentials: Push-token bearer credentials.
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state.
         *     :returns: Record id, server digest, issues and catalog path.
         */
        put: operations["put_candidate_api_v1_candidates_put"];
        /**
         * Post Candidate
         * @description Create a candidate; 409 ``candidate_exists`` if it already exists.
         *
         *     :param request: The request.
         *     :param response: The response.
         *     :param credentials: Push-token bearer credentials.
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state.
         *     :returns: Record id, server digest, issues and catalog path.
         */
        post: operations["post_candidate_api_v1_candidates_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/dev/token": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Dev Token
         * @description Mint a dev access token for the requested identity.
         *
         *     :param body: Subject, name, email and roles.
         *     :param settings: Application settings.
         *     :returns: The token and its lifetime in seconds.
         *     :raises AuthUnavailableError: If the shared secret is not set.
         */
        post: operations["create_dev_token_auth_dev_token_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ApprovalOut
         * @description Approval state of a record's current content, for the caller.
         */
        ApprovalOut: {
            state: components["schemas"]["ApprovalStateCode"];
            /** Needs Approval */
            needs_approval: boolean;
            /** Digest */
            digest: string;
            policy: components["schemas"]["PolicySummaryOut"];
            /** History */
            history: components["schemas"]["DecisionSummaryOut"][];
            /** Approvable */
            approvable: boolean;
            /** Approval Blocker */
            approval_blocker: string | null;
            /** Last Accepted Digest */
            last_accepted_digest: string | null;
            /** Can Decide */
            can_decide: boolean;
            /** Decide Blocked Code */
            decide_blocked_code: string | null;
            /** Decide Blocked Reason */
            decide_blocked_reason: string | null;
            divergence: components["schemas"]["DivergenceOut"] | null;
            /** Competing Candidates */
            competing_candidates: components["schemas"]["CompetingCandidateOut"][];
        };
        /**
         * ApprovalStateCode
         * @description The six approval states of a record's current content.
         * @enum {string}
         */
        ApprovalStateCode: "policy_missing" | "not_required" | "accepted" | "rejected" | "changed_since_acceptance" | "pending";
        /**
         * CandidateResultOut
         * @description Outcome of ``PUT``/``POST /api/v1/candidates``.
         */
        CandidateResultOut: {
            /**
             * Record Id
             * Format: uuid
             */
            record_id: string;
            /** Digest */
            digest: string;
            /** Created */
            created: boolean;
            /** Updated */
            updated: boolean;
            /** Deduplicated */
            deduplicated: boolean;
            /** Issues */
            issues: components["schemas"]["IssueOut"][];
            /** Catalog Path */
            catalog_path: string;
        };
        /**
         * CompetingCandidateOut
         * @description Another candidate of the identity with different content.
         */
        CompetingCandidateOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ref */
            ref: string;
            /** Path */
            path: string;
            /** Digest */
            digest: string;
            approval_state: components["schemas"]["ApprovalStateCode"];
        };
        /**
         * DecisionAction
         * @description Formal decision recorded by a reviewer.
         * @enum {string}
         */
        DecisionAction: "accepted" | "rejected";
        /**
         * DecisionIn
         * @description Body of ``POST /api/v1/records/{id}/decisions``.
         */
        DecisionIn: {
            action: components["schemas"]["DecisionAction"];
            /** Comment */
            comment?: string | null;
            /**
             * Expected Digest
             * @description Digest the reviewer saw; 409 `digest_changed` if the record's content changed since.
             */
            expected_digest?: string | null;
        };
        /**
         * DecisionProvenanceOut
         * @description The decided row as it was at decision time.
         */
        DecisionProvenanceOut: {
            /** Record Id */
            record_id: string | null;
            /** Kind */
            kind: string | null;
            /** Source Id */
            source_id: string | null;
            /** Project */
            project: string | null;
            /** Ref */
            ref: string | null;
            /** Path */
            path: string | null;
            /** Source Url */
            source_url: string | null;
        };
        /**
         * DecisionSummaryOut
         * @description One append-only decision event of the record's identity.
         */
        DecisionSummaryOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Digest */
            digest: string;
            /** Current Digest */
            current_digest: boolean;
            action: components["schemas"]["DecisionAction"];
            /** Actor Issuer */
            actor_issuer: string;
            /** Actor Subject */
            actor_subject: string;
            /** Actor Display */
            actor_display: string | null;
            /** Comment */
            comment: string | null;
            /** Policy Id */
            policy_id: string;
            /** Policy Version */
            policy_version: number;
            provenance: components["schemas"]["DecisionProvenanceOut"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * DevTokenIn
         * @description Identity to put into a dev token.
         */
        DevTokenIn: {
            /** Sub */
            sub: string;
            /** Name */
            name?: string | null;
            /** Email */
            email?: string | null;
            /** Roles */
            roles?: string[];
        };
        /**
         * DevTokenOut
         * @description A minted dev access token (OAuth 2 token-response shape).
         */
        DevTokenOut: {
            /** Access Token */
            access_token: string;
            /**
             * Token Type
             * @default Bearer
             */
            token_type: string;
            /** Expires In */
            expires_in: number;
        };
        /**
         * DiffEndpointOut
         * @description One side of a diff.
         */
        DiffEndpointOut: {
            /** Digest */
            digest: string;
            /** Label */
            label: string;
            /** Decided At */
            decided_at: string | null;
        };
        /**
         * DisplayStatus
         * @description Display status derived from inbound lifecycle links.
         * @enum {string}
         */
        DisplayStatus: "active" | "updated" | "obsoleted";
        /**
         * DivergenceKind
         * @description Kinds of published/accepted divergence (module docstring).
         * @enum {string}
         */
        DivergenceKind: "published_not_accepted" | "published_differs";
        /**
         * DivergenceOut
         * @description Content divergence within the record's identity.
         */
        DivergenceOut: {
            kind: components["schemas"]["DivergenceKind"];
            /** Other Digest */
            other_digest: string;
            /** Other Record Ids */
            other_record_ids: string[];
            /** Other Accepted */
            other_accepted: boolean;
            /** Message */
            message: string;
        };
        /**
         * ErrataSummaryOut
         * @description Counts of the record's errata for the top notice.
         *
         *     ``total``/``verified``/``reported``/``rejected``/``changed`` count
         *     published errata only (``not_required`` counts as verified);
         *     ``proposed`` counts candidate errata.
         */
        ErrataSummaryOut: {
            /** Total */
            total: number;
            /** Verified */
            verified: number;
            /** Reported */
            reported: number;
            /** Rejected */
            rejected: number;
            /** Changed */
            changed: number;
            /** Proposed */
            proposed: number;
        };
        /**
         * ErratumContentOut
         * @description The structured content of an erratum (on its own page).
         */
        ErratumContentOut: {
            type: components["schemas"]["ErratumType"] | null;
            /** Section */
            section: string | null;
            /** Reported By */
            reported_by: string | null;
            /** Reported Date */
            reported_date: string | null;
            /** Original Html */
            original_html: string | null;
            /** Corrected Html */
            corrected_html: string;
            /** Notes Html */
            notes_html: string | null;
        };
        /**
         * ErratumForOut
         * @description The decision an erratum corrects, resolved like outbound links.
         */
        ErratumForOut: {
            /**
             * Uuid
             * Format: uuid
             */
            uuid: string;
            /** Id */
            id: string | null;
            /** Title */
            title: string | null;
            /** Resolved */
            resolved: boolean;
        };
        /**
         * ErratumOut
         * @description One erratum (published or candidate) of the record being viewed.
         *
         *     ``approval_state`` is the erratum's own state: ``pending`` /
         *     ``policy_missing`` = reported, ``accepted`` = verified,
         *     ``rejected``, ``changed_since_acceptance``; ``not_required`` means
         *     no review is required. ``has_content`` is false (and the content
         *     fields empty) for a row stored before erratum content was.
         */
        ErratumOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["RecordState"];
            /** Ref */
            ref: string;
            /** Source Id */
            source_id: string;
            /** Project */
            project: string;
            /** Path */
            path: string;
            /** Title */
            title: string;
            type: components["schemas"]["ErratumType"] | null;
            /** Section */
            section: string | null;
            /** Reported By */
            reported_by: string | null;
            /** Reported Date */
            reported_date: string | null;
            /** Original Html */
            original_html: string | null;
            /** Corrected Html */
            corrected_html: string;
            /** Notes Html */
            notes_html: string | null;
            approval_state: components["schemas"]["ApprovalStateCode"];
            /** Digest */
            digest: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Has Content */
            has_content: boolean;
        };
        /**
         * ErratumType
         * @description Kind of correction an erratum reports.
         * @enum {string}
         */
        ErratumType: "technical" | "editorial";
        /**
         * FacetProjectOut
         * @description Record count of one project within a source.
         */
        FacetProjectOut: {
            /** Project */
            project: string;
            /** Count */
            count: number;
        };
        /**
         * FacetSourceOut
         * @description One source's projects, for the filter select.
         */
        FacetSourceOut: {
            /** Source Id */
            source_id: string;
            /** Count */
            count: number;
            /** Projects */
            projects: components["schemas"]["FacetProjectOut"][];
        };
        /**
         * FacetsOut
         * @description Filter options for the search UI.
         */
        FacetsOut: {
            /** Sources */
            sources: components["schemas"]["FacetSourceOut"][];
        };
        /**
         * FreshnessOut
         * @description Freshness of a record's owning registration.
         */
        FreshnessOut: {
            /** Last Attempt At */
            last_attempt_at: string | null;
            /** Last Success At */
            last_success_at: string | null;
            last_status: components["schemas"]["PollStatus"];
            /** Stale */
            stale: boolean;
            /** Intake */
            intake: components["schemas"]["IntakeKind"][];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * InboundLinkOut
         * @description A link from another record to the one being viewed.
         */
        InboundLinkOut: {
            link_type: components["schemas"]["InboundType"];
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
            /** Source Title */
            source_title: string;
        };
        /**
         * InboundType
         * @description Reverse names of the ``updates`` / ``obsoletes`` links.
         * @enum {string}
         */
        InboundType: "updated_by" | "obsoleted_by";
        /**
         * IntakeKind
         * @description How content entered the catalog.
         * @enum {string}
         */
        IntakeKind: "poll" | "push";
        /**
         * IssueCode
         * @description Stable machine-readable validation issue codes.
         * @enum {string}
         */
        IssueCode: "bad_yaml" | "missing_frontmatter" | "missing_uuid" | "bad_uuid" | "bad_date" | "missing_date" | "unknown_field" | "bad_field_type" | "duplicate_uuid" | "missing_target" | "ambiguous_target" | "legacy_alias" | "legacy_signoff" | "corrects_on_non_erratum" | "erratum_without_target" | "bad_encoding" | "bad_erratum_type" | "erratum_missing_corrected_text" | "erratum_unknown_section_heading" | "legacy_erratum_format";
        /**
         * IssueCountsOut
         * @description Stored-issue counts of one record, by severity.
         */
        IssueCountsOut: {
            /** Error */
            error: number;
            /** Warning */
            warning: number;
        };
        /**
         * IssueOut
         * @description One validation finding.
         */
        IssueOut: {
            severity: components["schemas"]["Severity"];
            code: components["schemas"]["IssueCode"];
            /** Message */
            message: string;
        };
        JsonValue: JsonValue;
        /**
         * LinkType
         * @description Outbound relationship types, named as written in frontmatter.
         * @enum {string}
         */
        LinkType: "updates" | "obsoletes" | "corrects";
        /**
         * MeOut
         * @description The authenticated caller and what they may do.
         */
        MeOut: {
            /** Issuer */
            issuer: string;
            /** Subject */
            subject: string;
            /** Display */
            display: string;
            /** Email */
            email: string | null;
            /** Roles */
            roles: string[];
            /** Permissions */
            permissions: components["schemas"]["Permission"][];
            reviewer: components["schemas"]["ReviewerOut"];
        };
        /**
         * MetadataOut
         * @description Identity and authored metadata of one record.
         */
        MetadataOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Adr Uuid */
            adr_uuid: string | null;
            /** Decision Date */
            decision_date: string | null;
            /** Decision Date Inferred */
            decision_date_inferred: boolean;
            kind: components["schemas"]["RecordState"];
            record_kind: components["schemas"]["RecordKind"];
            /** Title */
            title: string;
            title_source: components["schemas"]["TitleSource"];
            /** Digest */
            digest: string;
            /** Previous Digest */
            previous_digest: string | null;
        };
        /**
         * OutboundLinkOut
         * @description One outbound link and how it resolved.
         */
        OutboundLinkOut: {
            link_type: components["schemas"]["LinkType"];
            /**
             * Target Uuid
             * Format: uuid
             */
            target_uuid: string;
            /** Target Id */
            target_id: string | null;
            /** Target Title */
            target_title: string | null;
            resolution: components["schemas"]["Resolution"] | null;
            /** Ambiguous */
            ambiguous: boolean;
            /** Candidate Ids */
            candidate_ids: string[];
        };
        /**
         * Permission
         * @description Permissions an IdP role can grant (review comes from the policy).
         * @enum {string}
         */
        Permission: "read" | "operate";
        /**
         * PolicyStatus
         * @description Configuration status of the global approval policy.
         * @enum {string}
         */
        PolicyStatus: "configured" | "missing" | "invalid";
        /**
         * PolicySummaryOut
         * @description The applicable approval policy, or why there is none.
         */
        PolicySummaryOut: {
            status: components["schemas"]["PolicyStatus"];
            /** Id */
            id: string | null;
            /** Version */
            version: number | null;
            /** Required */
            required: boolean | null;
            /** Allow Self Approval */
            allow_self_approval: boolean | null;
        };
        /**
         * PollAcceptedOut
         * @description An accepted background poll.
         */
        PollAcceptedOut: {
            /** Accepted */
            accepted: string[];
            /** Message */
            message: string;
        };
        /**
         * PollStatus
         * @description Outcome of the latest poll of a registration.
         * @enum {string}
         */
        PollStatus: "never" | "ok" | "partial" | "failed" | "disabled";
        /**
         * ProvenanceOut
         * @description Where a record's content came from.
         */
        ProvenanceOut: {
            /** Source Id */
            source_id: string;
            /** Project */
            project: string;
            /** Path */
            path: string;
            /** Ref */
            ref: string;
            /** Source Url */
            source_url: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * RecordDetailOut
         * @description Everything the record detail page shows.
         */
        RecordDetailOut: {
            metadata: components["schemas"]["MetadataOut"];
            /** Issues */
            issues: components["schemas"]["IssueOut"][];
            /** Rendered Html */
            rendered_html: string;
            provenance: components["schemas"]["ProvenanceOut"];
            freshness: components["schemas"]["FreshnessOut"];
            /** Outbound Links */
            outbound_links: components["schemas"]["OutboundLinkOut"][];
            /** Inbound Links */
            inbound_links: components["schemas"]["InboundLinkOut"][];
            /** Errata */
            errata: components["schemas"]["ErratumOut"][];
            errata_summary: components["schemas"]["ErrataSummaryOut"];
            erratum: components["schemas"]["ErratumContentOut"] | null;
            erratum_for: components["schemas"]["ErratumForOut"] | null;
            status: components["schemas"]["DisplayStatus"];
            /** Siblings */
            siblings: components["schemas"]["SiblingOut"][];
            /** Legacy Signoff Unverified */
            legacy_signoff_unverified: string[];
            approval: components["schemas"]["ApprovalOut"];
        };
        /**
         * RecordDiffOut
         * @description A unified diff between two stored snapshots.
         */
        RecordDiffOut: {
            base: components["schemas"]["DiffEndpointOut"] | null;
            target: components["schemas"]["DiffEndpointOut"];
            /** Reason */
            reason: string | null;
            /** Unified Diff */
            unified_diff: string;
            /** Identical */
            identical: boolean;
            /** Lines Added */
            lines_added: number;
            /** Lines Removed */
            lines_removed: number;
        };
        /**
         * RecordKind
         * @description Kind of ADR record.
         * @enum {string}
         */
        RecordKind: "decision" | "erratum";
        /**
         * RecordState
         * @description Lifecycle state of a stored record row.
         * @enum {string}
         */
        RecordState: "published" | "candidate";
        /**
         * RecordTypeFilter
         * @description Which record kinds a search returns.
         * @enum {string}
         */
        RecordTypeFilter: "decision" | "erratum" | "all";
        /**
         * Resolution
         * @description Tier at which an outbound link was resolved.
         * @enum {string}
         */
        Resolution: "same_project" | "same_registration" | "global";
        /**
         * ReviewerOut
         * @description Whether the caller may record approval decisions, and why.
         */
        ReviewerOut: {
            /** Eligible */
            eligible: boolean;
            /** Reason */
            reason: string;
        };
        /**
         * SearchItemOut
         * @description One search result row.
         */
        SearchItemOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
            /** Source Id */
            source_id: string;
            /** Project */
            project: string;
            /** Path */
            path: string;
            /** Ref */
            ref: string;
            kind: components["schemas"]["RecordState"];
            record_kind: components["schemas"]["RecordKind"];
            approval_state: components["schemas"]["ApprovalStateCode"];
            issue_counts: components["schemas"]["IssueCountsOut"];
            /** Erratum For Title */
            erratum_for_title: string | null;
        };
        /**
         * SearchPageOut
         * @description One page of search results.
         */
        SearchPageOut: {
            /** Items */
            items: components["schemas"]["SearchItemOut"][];
            /** Total */
            total: number;
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
        };
        /**
         * Severity
         * @description Severity of a validation issue.
         * @enum {string}
         */
        Severity: "error" | "warning";
        /**
         * SiblingOut
         * @description One published or candidate row sharing a record's identity.
         */
        SiblingOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["RecordState"];
            /** Source Id */
            source_id: string;
            /** Project */
            project: string;
            /** Path */
            path: string;
            /** Ref */
            ref: string;
            /** Digest */
            digest: string;
            /** Title */
            title: string;
            /** Decision Date */
            decision_date: string | null;
            /** Decision Date Inferred */
            decision_date_inferred: boolean;
            approval_state: components["schemas"]["ApprovalStateCode"];
        };
        /**
         * SourceOut
         * @description One source registration's configuration and freshness.
         */
        SourceOut: {
            /** Id */
            id: string;
            /** Type */
            type: string;
            /** Enabled */
            enabled: boolean;
            /** Config Error */
            config_error: string | null;
            /** Intake */
            intake: components["schemas"]["IntakeKind"][];
            /** Published Ref */
            published_ref: string;
            /** Last Attempt At */
            last_attempt_at: string | null;
            /** Last Success At */
            last_success_at: string | null;
            last_status: components["schemas"]["PollStatus"];
            last_error: components["schemas"]["JsonValue"];
            /** Stale */
            stale: boolean;
        };
        /**
         * TitleSource
         * @description Where the display title came from.
         * @enum {string}
         */
        TitleSource: "frontmatter" | "h1" | "filename";
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };};
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    healthz_healthz_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    get_me_api_v1_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
        };
    };
    list_records_api_v1_records_get: {
        parameters: {
            query?: {
                /** @description Free text search. */
                q?: string | null;
                /** @description Registration id. */
                source?: string | null;
                /** @description Project path. */
                project?: string | null;
                /** @description state */
                state?: components["schemas"]["RecordState"] | null;
                /** @description Only records whose current content does not satisfy the policy: pending, rejected, changed since acceptance, or policy missing. */
                needs_approval?: boolean;
                /** @description Which records to return: `decision` (default), `erratum`, or `all`. Combines with every other filter. */
                record_type?: components["schemas"]["RecordTypeFilter"];
                page?: number;
                page_size?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchPageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_record_api_v1_records__record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecordDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_record_diff_api_v1_records__record_id__diff_get: {
        parameters: {
            query?: {
                /** @description Base digest; default: last decided snapshot, else the previous revision. */
                from?: string | null;
                /** @description Target digest; default: the current digest. */
                to?: string | null;
            };
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecordDiffOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sources_api_v1_sources_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceOut"][];
                };
            };
        };
    };
    poll_all_sources_api_v1_sources_poll_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PollAcceptedOut"];
                };
            };
        };
    };
    poll_one_source_api_v1_sources__source_id__poll_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PollAcceptedOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_facets_api_v1_facets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FacetsOut"];
                };
            };
        };
    };
    post_decision_api_v1_records__record_id__decisions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DecisionSummaryOut"];
                };
            };
            /** @description Error body `{detail, code, hint}`. */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_candidate_api_v1_candidates_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    /** Source Id */
                    source_id: string;
                    /**
                     * Project
                     * @description Owning project path.
                     */
                    project: string;
                    /**
                     * Adr Uuid
                     * Format: uuid
                     * @description UUID of the pushed ADR.
                     */
                    adr_uuid: string;
                    /**
                     * Ref
                     * @description Branch/ref the content comes from.
                     */
                    ref: string;
                    /**
                     * Content
                     * @description The complete Markdown file.
                     */
                    content: string;
                    /**
                     * Path
                     * @description File path inside the project (for title/date fallbacks and provenance); default `<registration path>/<adr_uuid>.md`.
                     */
                    path?: string | null;
                    /**
                     * Delivery Id
                     * @description CI event/delivery id for retry dedup.
                     */
                    delivery_id?: string | null;
                    /**
                     * Author
                     * @description Author email (self-approval check).
                     */
                    author?: string | null;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidateResultOut"];
                };
            };
            /** @description Error body `{detail, code, hint}`. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    post_candidate_api_v1_candidates_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    /** Source Id */
                    source_id: string;
                    /**
                     * Project
                     * @description Owning project path.
                     */
                    project: string;
                    /**
                     * Adr Uuid
                     * Format: uuid
                     * @description UUID of the pushed ADR.
                     */
                    adr_uuid: string;
                    /**
                     * Ref
                     * @description Branch/ref the content comes from.
                     */
                    ref: string;
                    /**
                     * Content
                     * @description The complete Markdown file.
                     */
                    content: string;
                    /**
                     * Path
                     * @description File path inside the project (for title/date fallbacks and provenance); default `<registration path>/<adr_uuid>.md`.
                     */
                    path?: string | null;
                    /**
                     * Delivery Id
                     * @description CI event/delivery id for retry dedup.
                     */
                    delivery_id?: string | null;
                    /**
                     * Author
                     * @description Author email (self-approval check).
                     */
                    author?: string | null;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidateResultOut"];
                };
            };
            /** @description Error body `{detail, code, hint}`. */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Error body `{detail, code, hint}`. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    create_dev_token_auth_dev_token_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DevTokenIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DevTokenOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
