import { createApp } from "vue";

import App from "@/App.vue";
import { initAuth } from "@/composables/useAuth";
import vuetify from "@/plugins/vuetify";
import router from "@/router";

// Wire the API client's TokenProvider/401/success seams before any
// component can issue a request (idempotent; App.vue also calls this
// so component-level tests that mount App.vue directly stay covered).
initAuth();

const app = createApp(App);

app.use(router);
app.use(vuetify);

app.mount("#app");
