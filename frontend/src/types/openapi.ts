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
         *     :returns: A mapping with ``status``, ``database``, ``config``,
         *         ``policy`` and ``registrations`` keys.
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
         *     The ``needs_approval`` filter is not available yet; it arrives in
         *     phase 07 together with the decision/approval actions.
         *
         *     :param q: Free text (titles, bodies, UUIDs, paths); blank or
         *         omitted matches everything.
         *     :param source: Restrict to one registration id.
         *     :param project: Restrict to one project path.
         *     :param state: Restrict to ``published`` or ``candidate``.
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
         *     Decision history is included (read-only); recording a new decision
         *     arrives in phase 07.
         *
         *     :param record_id: Record id.
         *     :param provider: Storage provider (overridden by tests).
         *     :param runtime: Startup configuration state.
         *     :param settings: Application settings (for the stale threshold).
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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ApprovalOut
         * @description Approval state of a record's current content.
         */
        ApprovalOut: {
            state: components["schemas"]["ApprovalStateCode"];
            /** Needs Approval */
            needs_approval: boolean;
            policy: components["schemas"]["PolicySummaryOut"];
            /** History */
            history: components["schemas"]["DecisionSummaryOut"][];
        };
        /**
         * ApprovalStateCode
         * @description The six approval states of a record's current content.
         * @enum {string}
         */
        ApprovalStateCode: "policy_missing" | "not_required" | "accepted" | "rejected" | "changed_since_acceptance" | "pending";
        /**
         * DecisionAction
         * @description Formal decision recorded by a reviewer.
         * @enum {string}
         */
        DecisionAction: "accepted" | "rejected";
        /**
         * DecisionSummaryOut
         * @description One historical decision event, read-only in phase 05.
         */
        DecisionSummaryOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Digest */
            digest: string;
            action: components["schemas"]["DecisionAction"];
            /** Actor Display */
            actor_display: string | null;
            /** Comment */
            comment: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * DisplayStatus
         * @description Display status derived from inbound lifecycle links.
         * @enum {string}
         */
        DisplayStatus: "active" | "updated" | "obsoleted";
        /**
         * ErratumOut
         * @description One erratum record correcting the record being viewed.
         */
        ErratumOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Title */
            title: string;
        };
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
        IssueCode: "bad_yaml" | "missing_frontmatter" | "missing_uuid" | "bad_uuid" | "bad_date" | "missing_date" | "unknown_field" | "bad_field_type" | "duplicate_uuid" | "missing_target" | "ambiguous_target" | "legacy_alias" | "legacy_signoff" | "corrects_on_non_erratum" | "erratum_without_target" | "bad_encoding";
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
            status: components["schemas"]["DisplayStatus"];
            /** Siblings */
            siblings: components["schemas"]["SiblingOut"][];
            /** Legacy Signoff Unverified */
            legacy_signoff_unverified: string[];
            approval: components["schemas"]["ApprovalOut"];
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
         * Resolution
         * @description Tier at which an outbound link was resolved.
         * @enum {string}
         */
        Resolution: "same_project" | "same_registration" | "global";
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
}
