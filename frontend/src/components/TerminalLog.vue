<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Check, Copy, Loader2, Terminal } from 'lucide-vue-next'

const props = defineProps({
  logs: { type: Array, default: () => [] },
  running: { type: Boolean, default: false },
})

const scrollArea = ref(null)
const copied = ref(false)
let copyTimer = null

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    const element = scrollArea.value
    if (element) element.scrollTop = element.scrollHeight
  },
)

watch(
  () => props.running,
  async () => {
    await nextTick()
    const element = scrollArea.value
    if (element) element.scrollTop = element.scrollHeight
  },
)

function levelClass(level) {
  if (level === 'success') return 'bg-emerald-500/10 text-emerald-400'
  if (level === 'warn') return 'bg-amber-500/10 text-amber-300'
  return 'bg-sky-500/10 text-sky-300'
}

async function copyLogs() {
  const text = props.logs
    .map(
      (log, index) =>
        `[${String(index + 1).padStart(2, '0')}] [${log.step}] ${log.message} (+${log.ms ?? 0}ms)`,
    )
    .join('\n')
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copied.value = false
    }, 1600)
  } catch {
    copied.value = false
  }
}

onBeforeUnmount(() => {
  clearTimeout(copyTimer)
})
</script>

<template>
  <section class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-terminal">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/80 px-4 py-3">
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-rose-500/90"></span>
          <span class="h-2.5 w-2.5 rounded-full bg-amber-400/90"></span>
          <span class="h-2.5 w-2.5 rounded-full bg-emerald-400/90"></span>
        </div>
        <div class="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
          <Terminal class="h-3.5 w-3.5 text-emerald-400" />
          smartclean.log
        </div>
        <span class="rounded-full border border-slate-700 bg-slate-800/80 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-slate-400">
          {{ logs.length }} events
        </span>
      </div>

      <div class="flex items-center gap-2">
        <span v-if="running" class="inline-flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400">
          <Loader2 class="h-3 w-3 animate-spin" />
          PIPELINE RUNNING
        </span>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800/80 px-2 py-1 text-[10px] font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-700/80 disabled:opacity-40"
          :disabled="!logs.length"
          @click="copyLogs"
        >
          <Check v-if="copied" class="h-3 w-3 text-emerald-400" />
          <Copy v-else class="h-3 w-3" />
          {{ copied ? '已复制' : '复制日志' }}
        </button>
      </div>
    </div>

    <div
      ref="scrollArea"
      class="thin-scrollbar max-h-72 overflow-y-auto px-4 py-3 font-mono text-[11px] leading-6"
    >
      <div v-if="!logs.length" class="flex items-center gap-2 text-slate-500">
        <span class="text-emerald-500">$</span>
        等待载入数据集<span class="terminal-cursor ml-0.5 text-emerald-500">▌</span>
      </div>

      <div
        v-for="(log, index) in logs"
        :key="index"
        class="flex items-start gap-2 rounded px-1 py-0.5 transition-colors hover:bg-white/[0.03]"
      >
        <span class="w-6 shrink-0 select-none text-right text-[10px] tabular-nums text-slate-600">
          {{ String(index + 1).padStart(2, '0') }}
        </span>
        <span class="shrink-0 text-emerald-500">$</span>
        <span
          class="shrink-0 rounded px-1.5 text-[10px] font-semibold leading-5"
          :class="levelClass(log.level)"
        >
          {{ log.step }}
        </span>
        <span class="min-w-0 flex-1 break-words text-slate-300">{{ log.message }}</span>
        <span class="shrink-0 text-[10px] tabular-nums text-slate-500">+{{ log.ms ?? 0 }}ms</span>
      </div>

      <div v-if="running" class="mt-1 flex items-center gap-2 text-amber-300">
        <Loader2 class="h-3 w-3 animate-spin" />
        正在执行 Pandas 清洗流水线...
      </div>
      <div v-else-if="logs.length" class="mt-1 text-emerald-500">
        $
        <span class="terminal-cursor ml-0.5">▌</span>
      </div>
    </div>
  </section>
</template>
