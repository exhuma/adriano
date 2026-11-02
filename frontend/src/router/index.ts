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
      path: "/records/:id",
      name: "record",
      component: () => import("@/views/RecordView.vue"),
      props: true,
    },
    {
      path: "/sources",
      name: "sources",
      component: () => import("@/views/SourcesView.vue"),
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/NotFoundView.vue"),
    },
  ],
});

export default router;
