/** Application routes. Search terms and filters live in the query
 * string (`q`, `source`, `project`, `state`, `needs_approval`), so
 * the landing page is shareable by URL alone. */
import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      name: "search",
      component: () => import("@/views/SearchView.vue"),
    },
    {
      path: "/records/:uuid",
      name: "record",
      component: () => import("@/views/RecordView.vue"),
      props: true,
    },
    {
      // The ref is a git ref and may contain slashes, so it takes the
      // rest of the path. `ref` is a reserved attribute name in Vue,
      // so the view receives it as `candidateRef`.
      path: "/records/:uuid/candidates/:ref(.*)",
      name: "record-candidate",
      component: () => import("@/views/RecordView.vue"),
      props: (route) => ({
        uuid: route.params.uuid,
        candidateRef: route.params.ref,
      }),
    },
    {
      path: "/sources",
      name: "sources",
      component: () => import("@/views/SourcesView.vue"),
    },
    {
      path: "/not-indexed",
      name: "not-indexed",
      component: () => import("@/views/NotIndexedView.vue"),
    },
    {
      // The location is four query parameters (see
      // `utils/notIndexedPaths.ts`).
      path: "/not-indexed/entry",
      name: "not-indexed-entry",
      component: () => import("@/views/NotIndexedEntryView.vue"),
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/NotFoundView.vue"),
    },
  ],
});

export default router;
