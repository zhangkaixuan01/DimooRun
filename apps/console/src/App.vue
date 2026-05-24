<template>
  <main class="console-shell">
    <aside class="sidebar">
      <div class="brand">DimooRun</div>
      <nav aria-label="Primary">
        <a class="nav-item is-active" href="/">Dashboard</a>
        <a class="nav-item" href="/">Agents</a>
        <a class="nav-item" href="/">Runs</a>
        <a class="nav-item" href="/">Tasks</a>
      </nav>
    </aside>
    <section class="content">
      <p class="eyebrow">Runtime Control Plane</p>
      <h1>DimooRun Console</h1>
      <div class="status-row">
        <span>Server</span>
        <strong>Not connected</strong>
      </div>
    </section>
  </main>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  color: #172033;
  background: #f6f8fb;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.console-shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 240px 1fr;
}

.sidebar {
  border-right: 1px solid #dce2ea;
  background: #ffffff;
  padding: 24px 18px;
}

.brand {
  margin-bottom: 28px;
  font-size: 18px;
  font-weight: 700;
}

.nav-item {
  display: block;
  border-radius: 6px;
  color: #526071;
  padding: 10px 12px;
  text-decoration: none;
}

.nav-item + .nav-item {
  margin-top: 4px;
}

.nav-item.is-active {
  color: #0f172a;
  background: #edf2f7;
  font-weight: 600;
}

.content {
  padding: 48px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

h1 {
  margin: 0 0 28px;
  font-size: 32px;
  font-weight: 750;
}

.status-row {
  display: flex;
  max-width: 520px;
  justify-content: space-between;
  border: 1px solid #dce2ea;
  border-radius: 8px;
  background: #ffffff;
  padding: 16px 18px;
}

@media (max-width: 720px) {
  .console-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #dce2ea;
  }

  .content {
    padding: 28px 20px;
  }
}
</style>
