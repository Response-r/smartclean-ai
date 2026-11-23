<script setup>
import { computed } from 'vue'
import { Database, Sparkles } from 'lucide-vue-next'
import { COLUMN_ORDER, FIELD_META, formatFieldValue, isBlank } from '../constants'

const props = defineProps({
  variant: { type: String, default: 'raw' },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  flags: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  emptyTitle: { type: String, default: '暂无数据' },
  emptyHint: { type: String, default: '' },
})

const cellFlags = computed(() => {
  const map = {}
  for (const flag of props.flags) {
    if (flag.field) map[`${flag.row}:${flag.field}`] = flag
  }
  return map
})

const rowFlags = computed(() => {
  const map = {}
  for (const flag of props.flags) {
    if (!flag.field) map[flag.row] = flag
  }
  return map
})

const displayColumns = computed(() =>
  props.columns.length ? props.columns : COLUMN_ORDER,
)

const flaggedCellCount = computed(() => Object.keys(cellFlags.value).length)
const HeaderIcon = computed(() => (props.variant === 'raw' ? Database : Sparkles))

function flagFor(rowIndex, field) {
  return cellFlags.value[`${rowIndex}:${field}`] || null
}

function cellClass(rowIndex, field) {
  if (!flagFor(rowIndex, field)) return ''
  return props.variant === 'raw' ? 'cell-flagged-raw' : 'cell-flagged-clean'
}

function displayValue(rowIndex, field) {
  const value = props.rows[rowIndex]?.[field]
  if (isBlank(value)) return props.variant === 'raw' ? 'NaN' : '—'
  return formatFieldValue(field, value)
}
</script>

<template>
  <section class="panel overflow-hidden">
    <div class="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3.5">
      <div class="flex items-center gap-2.5">
        <div
          class="grid h-8 w-8 place-items-center rounded-lg"
          :class="
            variant === 'raw'
              ? 'bg-slate-100 text-slate-500'
              : 'bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100'
          "
        >
          <component :is="HeaderIcon" class="h-4 w-4" />
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-sm font-bold tracking-tight text-slate-900">{{ title }}</h2>
            <span
              class="badge-soft"
              :class="
                variant === 'raw'
                  ? 'bg-slate-100 text-slate-500'
                  : 'bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100'
              "
            >
              {{ rows.length }} 行
            </span>
          </div>
          <p class="mt-0.5 text-[11px] text-slate-400">{{ subtitle }}</p>
        </div>
      </div>

      <div class="flex items-center gap-3 text-[10px] font-medium text-slate-400">
        <span class="inline-flex items-center gap-1.5">
          <span
            class="h-2.5 w-2.5 rounded-sm"
            :class="variant === 'raw' ? 'bg-rose-200' : 'bg-emerald-200'"
          ></span>
          {{ variant === 'raw' ? '问题单元格' : '已修复单元格' }}
          <span class="font-semibold text-slate-500">{{ flaggedCellCount }}</span>
        </span>
        <span class="hidden h-3 w-px bg-slate-200 sm:block"></span>
        <span class="hidden sm:inline">{{ variant === 'raw' ? '悬停角标查看原因' : '数据已标准化' }}</span>
      </div>
    </div>

    <div v-if="loading" class="space-y-3 p-4">
      <div v-for="index in 7" :key="index" class="flex items-center gap-3">
        <div class="skeleton h-5 w-7 rounded"></div>
        <div class="skeleton h-5 w-20 rounded"></div>
        <div class="skeleton h-5 flex-1 rounded"></div>
        <div class="skeleton hidden h-5 w-24 rounded sm:block"></div>
        <div class="skeleton hidden h-5 w-16 rounded md:block"></div>
      </div>
    </div>

    <div
      v-else-if="!rows.length"
      class="flex flex-col items-center justify-center px-6 py-16 text-center"
    >
      <div class="grid h-12 w-12 place-items-center rounded-2xl bg-slate-50 text-slate-300 ring-1 ring-slate-100">
        <Database class="h-5 w-5" />
      </div>
      <p class="mt-3 text-sm font-semibold text-slate-600">{{ emptyTitle }}</p>
      <p v-if="emptyHint" class="mt-1 max-w-sm text-xs leading-5 text-slate-400">{{ emptyHint }}</p>
    </div>

    <div v-else class="thin-scrollbar max-h-[540px] overflow-auto">
      <table class="w-full min-w-[680px] border-collapse text-left text-xs">
        <thead class="sticky top-0 z-10 bg-slate-50/95 backdrop-blur">
          <tr class="border-b border-slate-200">
            <th class="w-14 px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              #
            </th>
            <th
              v-for="column in displayColumns"
              :key="column"
              class="whitespace-nowrap px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400"
            >
              {{ FIELD_META[column]?.label || column }}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr
            v-for="(row, rowIndex) in rows"
            :key="rowIndex"
            class="transition-colors hover:bg-slate-50/70"
            :class="variant === 'raw' && rowFlags[rowIndex] ? 'bg-rose-50/40' : ''"
          >
            <td class="whitespace-nowrap px-3 py-2.5 align-middle">
              <div class="flex items-center gap-1">
                <span class="text-[10px] font-medium tabular-nums text-slate-400">
                  {{ String(rowIndex + 1).padStart(2, '0') }}
                </span>
                <span
                  v-if="rowFlags[rowIndex]"
                  class="cursor-help rounded bg-rose-100 px-1 py-0.5 text-[8px] font-bold leading-none text-rose-600"
                  :title="rowFlags[rowIndex].hint"
                >
                  DUP
                </span>
              </div>
            </td>

            <td
              v-for="column in displayColumns"
              :key="column"
              class="whitespace-nowrap px-3 py-2.5 align-middle"
              :class="cellClass(rowIndex, column)"
              :title="flagFor(rowIndex, column)?.hint || ''"
            >
              <div class="flex items-center gap-1.5">
                <span
                  class="tabular-nums"
                  :class="[
                    column === 'player_id' ? 'font-mono text-[11px] text-slate-600' : 'text-slate-700',
                    variant === 'raw' && isBlank(row[column]) ? 'font-semibold text-rose-500' : '',
                  ]"
                >
                  {{ displayValue(rowIndex, column) }}
                </span>

                <span
                  v-if="flagFor(rowIndex, column)"
                  class="inline-grid h-3.5 w-3.5 shrink-0 cursor-help place-items-center rounded-full text-[9px] font-bold leading-none text-white shadow-sm"
                  :class="variant === 'raw' ? 'bg-rose-500' : 'bg-emerald-500'"
                  :title="flagFor(rowIndex, column).hint"
                >
                  {{ variant === 'raw' ? '!' : '✓' }}
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

