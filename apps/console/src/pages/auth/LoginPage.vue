<template>
  <main class="login-page">
    <header class="login-topbar">
      <div class="brand-lockup">
        <span class="brand-mark">D</span>
        <span>
          <strong>DimooRun</strong>
          <small>{{ t("runtimeControlPlane") }}</small>
        </span>
      </div>
      <span class="mode-chip" :data-mode="mode">{{ modeLabel }}</span>
    </header>

    <section class="login-panel" aria-labelledby="login-title">
      <form class="login-form" @submit.prevent="submit">
        <div class="form-heading">
          <p class="page-kicker">{{ t("identity") }}</p>
          <h1 id="login-title">{{ t("signIn") }}</h1>
          <p>{{ t("signInCopy") }}</p>
        </div>

        <label class="field">
          {{ t("email") }}
          <input v-model="email" class="input" autocomplete="username" type="email" />
        </label>
        <label class="field">
          {{ t("password") }}
          <input v-model="password" class="input" autocomplete="current-password" type="password" />
        </label>
        <section v-if="auth.error" class="auth-error">
          <strong>{{ auth.error.errorCode }}</strong>
          <span>{{ auth.error.message }}</span>
        </section>
        <button class="button primary login-submit" type="submit" :disabled="auth.loading">
          {{ auth.loading ? t("loading") : t("signIn") }}
        </button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { apiMode } from "../../api/client";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();
const email = ref(import.meta.env.VITE_DIMOORUN_LOGIN_EMAIL || "admin@local.dimoorun");
const password = ref("");
const mode = apiMode();
const modeLabel = computed(() => (mode === "live" ? t("live") : mode === "demo" ? t("demo") : t("offline")));

async function submit() {
  await auth.login(email.value, password.value);
  await router.push("/dashboard");
}
</script>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  grid-template-rows: auto 1fr;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--color-page-grid) 38%, transparent) 1px, transparent 1px),
    linear-gradient(180deg, color-mix(in srgb, var(--color-page-grid) 34%, transparent) 1px, transparent 1px),
    var(--color-page);
  background-size: 28px 28px;
}

.login-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  padding: 16px 22px;
  backdrop-filter: blur(10px);
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-accent) 86%, var(--color-info));
  color: oklch(98% 0.006 255);
  font-weight: 800;
  box-shadow: 0 10px 24px color-mix(in srgb, var(--color-accent) 22%, transparent);
}

.brand-lockup strong {
  display: block;
  line-height: 1.1;
}

.brand-lockup small {
  display: block;
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.mode-chip {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-muted);
  padding: 7px 10px;
  font-size: 12px;
  font-weight: 800;
}

.mode-chip[data-mode="live"] {
  border-color: color-mix(in srgb, var(--color-success) 34%, var(--color-border));
  color: var(--color-success);
}

.mode-chip[data-mode="offline"] {
  border-color: color-mix(in srgb, var(--color-warning) 38%, var(--color-border));
  color: var(--color-warning);
}

.login-panel {
  align-self: center;
  justify-self: center;
  width: min(420px, calc(100% - 40px));
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-accent-quiet) 82%, transparent), transparent 56%),
    var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.login-form {
  display: grid;
  gap: 15px;
  padding: 28px;
}

.form-heading {
  margin-bottom: 6px;
}

.form-heading h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.16;
}

.form-heading p:last-child {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.field {
  display: grid;
  gap: 7px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.auth-error {
  display: grid;
  gap: 4px;
  border: 1px solid color-mix(in srgb, var(--color-danger) 54%, var(--color-border));
  border-radius: var(--radius-sm);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  padding: 10px 11px;
  font-size: 12px;
}

.login-submit {
  width: 100%;
  min-height: 38px;
  margin-top: 2px;
}

@media (max-width: 860px) {
  .login-topbar {
    padding: 14px 16px;
  }

  .login-panel {
    align-self: start;
    width: min(420px, calc(100% - 28px));
    margin-top: 34px;
  }

  .login-form {
    padding: 24px;
  }
}
</style>
