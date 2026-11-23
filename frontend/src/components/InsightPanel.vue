<script setup>
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Lightbulb,
  Sparkles,
  TrendingUp,
} from 'lucide-vue-next'

defineProps({
  insights: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const LEVEL_META = {
  critical: {
    label: '风险预警',
    accent: 'bg-rose-500',
    iconBox: 'bg-rose-50 text-rose-600',
    chip: 'bg-rose-50 text-rose-600 ring-1 ring-inset ring-rose-100',
    icon: AlertTriangle,
  },
  warning: {
    label: '需关注',
    accent: 'bg-amber-500',
    iconBox: 'bg-amber-50 text-amber-600',
    chip: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-100',
    icon: AlertTriangle,
  },
  opportunity: {
    label: '增长机会',
    accent: 'bg-indigo-500',
    iconBox: 'bg-indigo-50 text-indigo-600',
    chip: 'bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100',
    icon: TrendingUp,
  },
  success: {
    label: '表现良好',
    accent: 'bg-emerald-500',
    iconBox: 'bg-emerald-50 text-emerald-600',
    chip: 'bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100',
    icon: CheckCircle2,
  },
}

function levelMeta(level) {
  return LEVEL_META[level] || LEVEL_META.opportunity
}
</script>

<template>
  <section class="panel overflow-hidden">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
      <div class="flex items-center gap-3">
        <div class="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-500/25">
          <Sparkles class="h-4 w-4" />
        </div>
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="text-sm font-bold tracking-tight text-slate-900">AI 业务诊断洞察</h2>
            <span class="badge-soft bg-violet-50 text-violet-600 ring-1 ring-inset ring-violet-100">
              <BrainCircuit class="h-3 w-3" />
              RULE ENGINE
            </span>
          </div>
          <p class="mt-0.5 text-[11px] text-slate-500">内置规则引擎 · 本地推理 · 无需外部 API Key，断网可用</p>
        </div>
      </div>
      <span class="badge-soft bg-slate-100 text-slate-500">
        {{ insights.length ? `${insights.length} 条洞察` : '等待分析' }}
      </span>
    </div>

    <div class="p-5">
      <div v-if="loading" class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div v-for="index in 3" :key="index" class="rounded-xl border border-slate-100 p-4">
          <div class="flex items-center justify-between">
            <div class="skeleton h-4 w-32 rounded"></div>
            <div class="skeleton h-4 w-16 rounded-full"></div>
          </div>
          <div class="skeleton mt-4 h-3 w-full rounded"></div>
          <div class="skeleton mt-2 h-3 w-11/12 rounded"></div>
          <div class="skeleton mt-2 h-3 w-4/5 rounded"></div>
          <div class="skeleton mt-4 h-12 w-full rounded-lg"></div>
          <div class="skeleton mt-4 h-5 w-28 rounded"></div>
        </div>
      </div>

      <div v-else-if="insights.length" class="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <article
          v-for="insight in insights"
          :key="insight.id"
          class="group relative overflow-hidden rounded-xl border border-slate-200/80 bg-white p-4 transition duration-200 hover:-translate-y-0.5 hover:shadow-md"
        >
          <span class="absolute inset-y-0 left-0 w-1" :class="levelMeta(insight.level).accent"></span>

          <div class="flex items-center justify-between gap-2 pl-1.5">
            <div class="flex min-w-0 items-center gap-2">
              <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg" :class="levelMeta(insight.level).iconBox">
                <component :is="levelMeta(insight.level).icon" class="h-3.5 w-3.5" />
              </span>
              <h3 class="truncate text-sm font-semibold text-slate-900" :title="insight.title">
                {{ insight.title }}
              </h3>
            </div>
            <span class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="levelMeta(insight.level).chip">
              {{ levelMeta(insight.level).label }}
            </span>
          </div>

          <p class="mt-3 pl-1.5 text-xs leading-6 text-slate-600">{{ insight.finding }}</p>

          <div class="mt-3 flex gap-2 rounded-lg bg-slate-50 p-2.5">
            <Lightbulb class="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
            <p class="text-xs leading-5 text-slate-600">
              <span class="font-semibold text-slate-700">运营建议：</span>{{ insight.suggestion }}
            </p>
          </div>

          <div class="mt-3 flex items-center justify-between pl-1.5">
            <span class="text-[10px] uppercase tracking-wider text-slate-400">{{ insight.metric?.label }}</span>
            <span class="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 ring-1 ring-inset ring-slate-200">
              {{ insight.metric?.value }}
            </span>
          </div>
        </article>
      </div>

      <div
        v-else
        class="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-10 text-center"
      >
        <div class="grid h-12 w-12 place-items-center rounded-2xl bg-white text-indigo-500 shadow-sm ring-1 ring-slate-100">
          <Sparkles class="h-5 w-5" />
        </div>
        <p class="mt-3 text-sm font-semibold text-slate-700">AI 洞察等待生成</p>
        <p class="mt-1 max-w-md text-xs leading-5 text-slate-400">
          加载数据后点击顶部「一键执行 AI 清洗」，系统会基于清洗结果输出 3 条市场、付费与数据质量诊断建议。
        </p>
      </div>
    </div>
  </section>
</template>
