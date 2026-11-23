<script setup>
import { computed } from 'vue'
import { BadgeCheck, Database, ShieldCheck, TrendingUp, Wrench } from 'lucide-vue-next'

const props = defineProps({
  metrics: { type: Object, default: null },
  preview: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
})

const TONES = {
  indigo: {
    iconBox: 'bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100',
    blob: 'bg-indigo-500',
  },
  emerald: {
    iconBox: 'bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100',
    blob: 'bg-emerald-500',
  },
  amber: {
    iconBox: 'bg-amber-50 text-amber-600 ring-1 ring-inset ring-amber-100',
    blob: 'bg-amber-500',
  },
  violet: {
    iconBox: 'bg-violet-50 text-violet-600 ring-1 ring-inset ring-violet-100',
    blob: 'bg-violet-500',
  },
}

const cards = computed(() => {
  const metrics = props.metrics
  const preview = props.preview || {}
  const rawTotal = metrics?.raw_total ?? preview.total ?? 0
  const issueCells = metrics?.raw_issue_cells ?? preview.issue_cells ?? 0
  const health = Number(metrics?.clean_health ?? preview.health ?? 0)
  const delta = Number(metrics?.health_delta ?? 0)
  const hasAnyData = rawTotal > 0
  const improvement =
    metrics && Number(metrics.raw_health) > 0
      ? (delta / Number(metrics.raw_health)) * 100
      : null

  return [
    {
      key: 'raw',
      tag: 'RAW',
      label: '原始总记录',
      value: rawTotal,
      suffix: '条',
      sub: rawTotal ? `体检发现 ${issueCells} 个问题单元格` : '尚未载入数据',
      icon: Database,
      tone: TONES.indigo,
      progress: null,
      delta: null,
    },
    {
      key: 'clean',
      tag: 'CLEAN',
      label: '有效清洗记录',
      value: metrics ? metrics.clean_total : '—',
      suffix: metrics ? '条' : '',
      sub: metrics ? `已移除 ${metrics.duplicate_removed} 条完全重复记录` : '执行 AI 清洗后实时展示',
      icon: BadgeCheck,
      tone: TONES.emerald,
      progress: null,
      delta: null,
    },
    {
      key: 'repaired',
      tag: 'FIXED',
      label: '修复异常 / 缺失数',
      value: metrics ? metrics.repaired_count : issueCells,
      suffix: '处',
      sub: metrics
        ? `缺失 ${metrics.missing_filled} · 异常 ${metrics.anomalies_fixed} · 格式 ${metrics.format_normalized}`
        : '待清洗问题总数',
      icon: Wrench,
      tone: TONES.amber,
      progress: null,
      delta: null,
    },
    {
      key: 'health',
      tag: 'HEALTH',
      label: '数据健康度评分',
      value: hasAnyData ? health.toFixed(1) : '—',
      suffix: hasAnyData ? '分' : '',
      sub: metrics
        ? `原始 ${metrics.raw_health} 分 → 清洗后 ${metrics.clean_health} 分`
        : '原始数据健康度 · 清洗后自动复评',
      icon: ShieldCheck,
      tone: TONES.violet,
      progress: hasAnyData ? Math.max(4, Math.min(100, health)) : 0,
      delta: improvement !== null && improvement > 0 ? improvement : null,
    },
  ]
})
</script>

<template>
  <section class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <template v-if="loading">
      <div v-for="index in 4" :key="index" class="panel p-5">
        <div class="flex items-start justify-between">
          <div class="skeleton h-10 w-10 rounded-xl"></div>
          <div class="skeleton h-4 w-12 rounded"></div>
        </div>
        <div class="skeleton mt-5 h-7 w-24 rounded-md"></div>
        <div class="skeleton mt-3 h-3 w-40 rounded"></div>
        <div class="skeleton mt-5 h-2 w-full rounded-full"></div>
      </div>
    </template>

    <template v-else>
      <article
        v-for="card in cards"
        :key="card.key"
        class="panel group relative overflow-hidden p-5 transition duration-300 hover:-translate-y-0.5 hover:shadow-glow"
      >
        <div
          class="pointer-events-none absolute -right-6 -top-8 h-24 w-24 rounded-full opacity-[0.08] blur-2xl"
          :class="card.tone.blob"
        ></div>

        <div class="flex items-start justify-between gap-2">
          <div class="grid h-10 w-10 place-items-center rounded-xl" :class="card.tone.iconBox">
            <component :is="card.icon" class="h-5 w-5" />
          </div>
          <div class="flex items-center gap-2">
            <span
              v-if="card.delta !== null"
              class="badge-soft bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100"
              :title="`较原始健康度提升 ${card.delta.toFixed(1)}%`"
            >
              <TrendingUp class="h-3 w-3" />
              +{{ card.delta.toFixed(1) }}%
            </span>
            <span class="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
              {{ card.tag }}
            </span>
          </div>
        </div>

        <p class="mt-4 text-xs font-medium text-slate-500">{{ card.label }}</p>
        <p class="mt-1 flex items-baseline gap-1.5">
          <span class="text-[28px] font-bold leading-none tracking-tight text-slate-900 tabular-nums">
            {{ card.value }}
          </span>
          <span v-if="card.suffix" class="text-sm font-semibold text-slate-400">{{ card.suffix }}</span>
        </p>
        <p class="mt-2 truncate text-[11px] text-slate-400" :title="card.sub">{{ card.sub }}</p>

        <div v-if="card.progress !== null" class="mt-4">
          <div class="flex items-center justify-between text-[10px] font-medium text-slate-400">
            <span class="tracking-wider">HEALTH SCORE</span>
            <span class="text-slate-500">{{ card.value }} / 100</span>
          </div>
          <div class="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-full rounded-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-emerald-400 transition-all duration-700 ease-out"
              :style="{ width: `${card.progress}%` }"
            ></div>
          </div>
        </div>
      </article>
    </template>
  </section>
</template>
