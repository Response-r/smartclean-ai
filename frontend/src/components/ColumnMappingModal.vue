<script setup>
import { computed, reactive, watch } from 'vue'
import { AlertTriangle, ArrowRightLeft, Check, Database, Loader2, Sparkles, X } from 'lucide-vue-next'
import { COLUMN_ORDER, FIELD_META } from '../constants'

const DEFAULT_OPTION = '__default__'

const props = defineProps({
  open: { type: Boolean, default: false },
  inspection: { type: Object, default: null },
  confirming: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])
const selection = reactive({})

watch(
  () => props.inspection,
  (inspection) => {
    for (const key of Object.keys(selection)) delete selection[key]
    if (!inspection) return
    for (const field of COLUMN_ORDER) {
      const suggested = inspection.suggested_mapping?.[field]
      selection[field] = suggested || ''
    }
  },
  { immediate: true },
)

const sourceColumns = computed(() => props.inspection?.source_columns || [])
const sampleRows = computed(() => props.inspection?.sample_rows || [])
const suggested = computed(() => props.inspection?.suggested_mapping || {})
const autoMappedCount = computed(() => props.inspection?.auto_mapped_count || 0)

const duplicateSources = computed(() => {
  const counts = {}
  for (const field of COLUMN_ORDER) {
    const value = selection[field]
    if (value && value !== DEFAULT_OPTION) counts[value] = (counts[value] || 0) + 1
  }
  return Object.keys(counts).filter((source) => counts[source] > 1)
})

const unmappedFields = computed(() => COLUMN_ORDER.filter((field) => !selection[field]))
const defaultFields = computed(() => COLUMN_ORDER.filter((field) => selection[field] === DEFAULT_OPTION))
const manualCount = computed(
  () => COLUMN_ORDER.filter((field) => selection[field] && selection[field] !== DEFAULT_OPTION).length,
)
const canConfirm = computed(
  () => !props.confirming && !unmappedFields.value.length && !duplicateSources.value.length,
)

const STATUS_META = {
  unmapped: 'bg-rose-50 text-rose-600 ring-1 ring-inset ring-rose-100',
  default: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-100',
  auto: 'bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100',
  manual: 'bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100',
}

function fieldStatus(field) {
  const value = selection[field]
  if (!value) return { label: '待映射', classes: STATUS_META.unmapped }
  if (value === DEFAULT_OPTION) return { label: '默认值', classes: STATUS_META.default }
  if (suggested.value[field] && suggested.value[field] === value) {
    return { label: '自动识别', classes: STATUS_META.auto }
  }
  return { label: '手动指定', classes: STATUS_META.manual }
}

function isOptionDisabled(field, sourceName) {
  return COLUMN_ORDER.some((other) => other !== field && selection[other] === sourceName)
}

function displaySample(value) {
  if (value === null || value === undefined || value === '') return 'NaN'
  const text = String(value)
  return text.length > 26 ? `${text.slice(0, 26)}…` : text
}

function onSubmit() {
  if (!canConfirm.value) return
  const mapping = {}
  for (const field of COLUMN_ORDER) mapping[field] = selection[field]
  emit('confirm', mapping)
}

function onCancel() {
  if (props.confirming) return
  emit('cancel')
}
</script>

<template>
  <Transition name="fade">
    <div
      v-if="open && inspection"
      class="fixed inset-0 z-[65] flex items-center justify-center bg-slate-950/60 p-3 backdrop-blur-sm sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="mapping-title"
      @click.self="onCancel"
    >
      <div class="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div class="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div class="flex min-w-0 items-center gap-3">
            <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-500/25">
              <ArrowRightLeft class="h-5 w-5" />
            </div>
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h2 id="mapping-title" class="text-base font-bold tracking-tight text-slate-900">字段映射</h2>
                <span class="badge-soft bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
                  SMART MAPPING
                </span>
              </div>
              <p class="mt-0.5 truncate text-xs text-slate-500" :title="inspection.filename">
                {{ inspection.filename }} · {{ inspection.total_rows }} 行 · {{ sourceColumns.length }} 列
              </p>
            </div>
          </div>
          <button
            type="button"
            class="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40"
            :disabled="confirming"
            aria-label="关闭字段映射"
            @click="onCancel"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <div class="thin-scrollbar flex-1 overflow-y-auto px-5 py-4">
          <div
            class="flex flex-col gap-2 rounded-xl border px-3.5 py-3 sm:flex-row sm:items-center sm:justify-between"
            :class="
              autoMappedCount === COLUMN_ORDER.length
                ? 'border-emerald-200 bg-emerald-50/70'
                : 'border-indigo-200 bg-indigo-50/60'
            "
          >
            <div class="flex items-start gap-2.5">
              <Sparkles
                class="mt-0.5 h-4 w-4 shrink-0"
                :class="autoMappedCount === COLUMN_ORDER.length ? 'text-emerald-600' : 'text-indigo-600'"
              />
              <div>
                <p class="text-xs font-semibold text-slate-700">
                  已自动识别 {{ autoMappedCount }} / {{ COLUMN_ORDER.length }} 个标准字段
                </p>
                <p class="mt-0.5 text-[11px] leading-5 text-slate-500">
                  请把源列映射到看板需要的 7 个字段；没有对应列时可显式选择「使用默认值」，但业务洞察可能失真。
                </p>
              </div>
            </div>
            <span class="badge-soft shrink-0 bg-white text-slate-500 ring-1 ring-inset ring-slate-200">
              解析耗时 {{ inspection.parse_ms }}ms
            </span>
          </div>

          <div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div
              v-for="field in COLUMN_ORDER"
              :key="field"
              class="rounded-xl border border-slate-200 bg-white p-3 transition hover:border-indigo-200 hover:shadow-sm"
            >
              <div class="flex items-center justify-between gap-2">
                <div class="min-w-0">
                  <label class="text-xs font-semibold text-slate-700">
                    {{ FIELD_META[field].label }}
                    <span class="text-rose-500">*</span>
                  </label>
                  <p class="mt-0.5 font-mono text-[10px] text-slate-400">{{ field }}</p>
                </div>
                <span class="badge-soft shrink-0" :class="fieldStatus(field).classes">
                  {{ fieldStatus(field).label }}
                </span>
              </div>

              <select
                v-model="selection[field]"
                class="mt-2.5 w-full rounded-lg border border-slate-200 bg-slate-50/60 px-2.5 py-2 text-xs text-slate-700 outline-none transition focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100"
                :aria-label="`${FIELD_META[field].label}映射源字段`"
              >
                <option value="">— 请选择源字段 —</option>
                <option
                  v-for="column in sourceColumns"
                  :key="column.name"
                  :value="column.name"
                  :disabled="isOptionDisabled(field, column.name)"
                >
                  {{ column.name }}（{{ column.dtype }}）
                </option>
                <option :value="DEFAULT_OPTION">— 使用默认值（不推荐）—</option>
              </select>

              <p class="mt-1.5 truncate text-[10px] text-slate-400" :title="suggested[field] || ''">
                <template v-if="suggested[field]">自动建议：{{ suggested[field] }}</template>
                <template v-else-if="selection[field] === DEFAULT_OPTION">将生成占位数据</template>
                <template v-else>暂无自动建议</template>
              </p>
            </div>
          </div>

          <div class="mt-5 overflow-hidden rounded-xl border border-slate-200">
            <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/70 px-3.5 py-2.5">
              <div class="flex items-center gap-2 text-xs font-semibold text-slate-700">
                <Database class="h-3.5 w-3.5 text-slate-400" />
                源数据预览
                <span class="text-[10px] font-normal text-slate-400">前 {{ sampleRows.length }} 行</span>
              </div>
              <span class="text-[10px] text-slate-400">横向滚动可查看全部源列</span>
            </div>
            <div class="thin-scrollbar max-h-56 overflow-auto">
              <table class="min-w-max border-collapse text-left text-[11px]">
                <thead class="sticky top-0 z-10 bg-white/95 backdrop-blur">
                  <tr class="border-b border-slate-100">
                    <th class="whitespace-nowrap px-3 py-2 text-[10px] font-semibold text-slate-400">#</th>
                    <th
                      v-for="column in sourceColumns"
                      :key="column.name"
                      class="whitespace-nowrap px-3 py-2 text-[10px] font-semibold text-slate-400"
                    >
                      {{ column.name }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="(row, rowIndex) in sampleRows" :key="rowIndex" class="hover:bg-slate-50/60">
                    <td class="whitespace-nowrap px-3 py-2 tabular-nums text-slate-400">
                      {{ String(rowIndex + 1).padStart(2, '0') }}
                    </td>
                    <td
                      v-for="column in sourceColumns"
                      :key="column.name"
                      class="whitespace-nowrap px-3 py-2 text-slate-600"
                      :title="row[column.name] === null ? 'NaN' : String(row[column.name])"
                    >
                      {{ displaySample(row[column.name]) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="mt-4 space-y-2">
            <div
              v-if="duplicateSources.length"
              class="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-[11px] leading-5 text-rose-700"
            >
              <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>同一源字段不能重复映射：{{ duplicateSources.join('、') }}。请为不同目标字段选择不同源列。</p>
            </div>
            <div
              v-if="unmappedFields.length"
              class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-[11px] leading-5 text-amber-700"
            >
              <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                还有 {{ unmappedFields.length }} 个字段未映射：
                {{ unmappedFields.map((field) => FIELD_META[field].label).join('、') }}。
                请选择源列，或显式选择「使用默认值」。
              </p>
            </div>
            <div
              v-if="defaultFields.length"
              class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-[11px] leading-5 text-amber-700"
            >
              <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                将对 {{ defaultFields.map((field) => FIELD_META[field].label).join('、') }} 使用默认值填充。
                这会让对应维度的业务洞察失真，仅建议用于验证上传与清洗链路。
              </p>
            </div>
            <div
              v-if="!duplicateSources.length && !unmappedFields.length && !defaultFields.length"
              class="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-[11px] leading-5 text-emerald-700"
            >
              <Check class="h-3.5 w-3.5 shrink-0" />
              <p>7 个标准字段均已映射，可以确认导入。</p>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/70 px-5 py-3">
          <p class="text-[11px] text-slate-400">
            自动识别 {{ autoMappedCount }}/{{ COLUMN_ORDER.length }} ·
            已映射 {{ manualCount }} ·
            默认值 {{ defaultFields.length }}
          </p>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="btn-secondary !py-2 text-xs"
              :disabled="confirming"
              @click="onCancel"
            >
              取消
            </button>
            <button
              type="button"
              class="btn-primary !py-2 text-xs"
              :disabled="!canConfirm"
              @click="onSubmit"
            >
              <Loader2 v-if="confirming" class="h-3.5 w-3.5 animate-spin" />
              <Check v-else class="h-3.5 w-3.5" />
              {{ confirming ? '正在导入...' : '确认映射并载入' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
