<template>
  <div class="table-wrap data-table">
    <table :aria-label="label">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            :class="[column.headerClass, column.align ? `align-${column.align}` : null]"
            scope="col"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(rowIdentity(row))"
          class="data-table-row"
          :class="{
            selectable,
            selected: selectedKey !== null && selectedKey !== undefined && rowIdentity(row) === selectedKey,
          }"
          :data-selected="rowIdentity(row) === selectedKey ? 'true' : 'false'"
          :tabindex="selectable ? 0 : undefined"
          :aria-selected="selectable ? rowIdentity(row) === selectedKey : undefined"
          @click="selectRow(row)"
          @keydown.enter="selectRow(row)"
          @keydown.space.prevent="selectRow(row)"
        >
          <td
            v-for="column in columns"
            :key="column.key"
            :data-label="column.label"
            :class="[column.cellClass, column.align ? `align-${column.align}` : null]"
          >
            <slot
              :name="`cell-${column.key}`"
              :row="row"
              :value="valueFor(row, column.key)"
            >
              {{ formatValue(valueFor(row, column.key)) }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
type TableRow = any;

type Column = {
  key: string;
  label: string;
  align?: "start" | "center" | "end";
  headerClass?: string;
  cellClass?: string;
};

const props = withDefaults(defineProps<{
  columns: Column[];
  rows: TableRow[];
  rowKey: string | ((row: TableRow) => string | number);
  selectedKey?: string | number | null;
  selectable?: boolean;
  label?: string;
}>(), {
  selectedKey: null,
  selectable: false,
  label: "",
});

const emit = defineEmits<{
  rowSelect: [row: TableRow];
}>();

function rowIdentity(row: TableRow): string | number {
  return typeof props.rowKey === "function" ? props.rowKey(row) : String(row[props.rowKey] ?? "");
}

function valueFor(row: TableRow, key: string): unknown {
  return row[key];
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function selectRow(row: TableRow) {
  if (!props.selectable) return;
  emit("rowSelect", row);
}
</script>

<style scoped>
.data-table-row.selectable {
  cursor: pointer;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.data-table-row.selectable td {
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.data-table-row.selectable:hover,
.data-table-row.selectable:focus-visible {
  background: color-mix(in oklab, var(--color-primary) 8%, transparent);
  outline: none;
}

.data-table-row.selected,
.data-table-row[data-selected="true"] {
  background: var(--color-accent-soft);
}

.data-table-row.selected td,
.data-table-row[data-selected="true"] td {
  background: var(--color-accent-soft) !important;
}

.data-table-row.selected td:first-child,
.data-table-row[data-selected="true"] td:first-child {
  box-shadow: inset 3px 0 0 var(--color-primary) !important;
}

.align-center {
  text-align: center;
}

.align-end {
  text-align: right;
}

@media (max-width: 900px) {
  .data-table table,
  .data-table thead,
  .data-table tbody,
  .data-table th,
  .data-table td,
  .data-table tr {
    display: block;
  }

  .data-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .data-table tbody {
    display: grid;
    gap: 12px;
  }

  .data-table tr {
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-surface);
    overflow: hidden;
  }

  .data-table td {
    display: grid;
    grid-template-columns: minmax(116px, 42%) minmax(0, 1fr);
    gap: 12px;
    align-items: start;
    border-bottom: 1px solid var(--color-border);
    padding: 12px 14px;
    text-align: left;
  }

  .data-table td:last-child {
    border-bottom: 0;
  }

  .data-table td::before {
    content: attr(data-label);
    color: var(--color-text-muted);
    font-size: 0.76rem;
    font-weight: 800;
  }

  .data-table .align-end,
  .data-table .align-center {
    text-align: left;
  }
}
</style>
