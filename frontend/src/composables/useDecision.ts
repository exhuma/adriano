/**
 * Core decide-flow logic (module-interaction-core "Intents & ports").
 *
 * Submits an accept/reject decision bound to the exact digest the
 * reviewer saw and resolves to a typed, delivery-agnostic outcome --
 * never throws. This composable owns no wording, no confirmation UX,
 * and no focus management: `DecisionDialog.vue` is the only adapter,
 * and it is the one place allowed to phrase the question, render a
 * modal, and decide what Cancel/Escape do. Submitting is modelled as
 * one intent ("decide this digest"), not as "open a dialog and post
 * if confirmed".
 */
import { ref } from "vue";

import { ApiError } from "@/api";
import { postDecision } from "@/api/decisions";
import type { DecisionAction, DecisionSummaryOut } from "@/types/approval";
import { errorCode, errorDetail, errorHint } from "@/utils/apiErrors";

/** A decision was recorded. */
export interface DecisionSuccess {
  kind: "success";
  event: DecisionSummaryOut;
}

/** The content changed since the reviewer loaded it (409
 *  `digest_changed`): there is nothing to retry, the record must be
 *  reloaded and re-reviewed. */
export interface DecisionDigestChanged {
  kind: "digest_changed";
  message: string;
}

/** Any other refusal (403/404/409), with the server's own wording. */
export interface DecisionError {
  kind: "error";
  code: string | undefined;
  message: string;
  hint: string | undefined;
}

/** Outcome of one decision submission. */
export type DecisionOutcome =
  | DecisionSuccess
  | DecisionDigestChanged
  | DecisionError;

/** Decide-flow state and the one action it exposes. */
export function useDecision() {
  const submitting = ref(false);

  /**
   * Submit an accept/reject decision for one record's exact digest.
   *
   * :param recordId: Record id.
   * :param action: `"accepted"` or `"rejected"`.
   * :param expectedDigest: The digest shown to the reviewer; the
   *     server refuses with `digest_changed` if the content moved on.
   * :param comment: Optional reviewer comment (trimmed; blank means
   *     none).
   * :returns: A typed outcome; this function never throws.
   */
  async function decide(
    recordId: string,
    action: DecisionAction,
    expectedDigest: string,
    comment?: string,
  ): Promise<DecisionOutcome> {
    submitting.value = true;
    try {
      const trimmed = comment?.trim();
      const event = await postDecision(recordId, {
        action,
        comment: trimmed ? trimmed : undefined,
        expected_digest: expectedDigest,
      });
      return { kind: "success", event };
    } catch (error) {
      if (error instanceof ApiError) {
        const code = errorCode(error);
        const message =
          errorDetail(error) ?? "The decision could not be recorded.";
        if (code === "digest_changed") {
          return { kind: "digest_changed", message };
        }
        return { kind: "error", code, message, hint: errorHint(error) };
      }
      return {
        kind: "error",
        code: undefined,
        message:
          "The decision could not be recorded. Check your connection " +
          "and try again.",
        hint: undefined,
      };
    } finally {
      submitting.value = false;
    }
  }

  return { submitting, decide };
}
