<script setup>
import { computed, ref } from 'vue'
import {
  DatabaseZap,
  Download,
  Loader2,
  RefreshCw,
  Sparkles,
  UploadCloud,
  Wand2,
} from 'lucide-vue-next'

const props = defineProps({
  hasData: { type: Boolean, default: false },
  hasCleaned: { type: Boolean, default: false },
  backendStatus: { type: String, default: 'checking' },
  loading: {
    type: Object,
    default: () => ({ load: false, upload: false, clean: false, export: false, mapping: false }),
  },
})

const emit = defineEmits(['load-mock', 'upload-file', 'clean', 'export', 'retry'])
const fileInput = ref(null)

const statusMeta = computed(() => {
  const map = {
    checking: {
      label: '连接后端中',
      dot: 'bg-amber-400',
      ping: 'bg-amber-400',
      pill: 'border-amber-200 bg-amber-50 text-amber-700',
    },
    online: {
      label: '后端已连接',
      dot: 'bg-emerald-500',
      ping: 'bg-emerald-400',
      pill: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    },
    offline: {
      label: '后端未连接 · 重试',
      dot: 'bg-rose-500',
      ping: 'bg-rose-400',
      pill: 'border-rose-200 bg-rose-50 text-rose-700',
    },
  }
  return map[props.backendStatus] || map.checking
})

function pickFile() {
  fileInput.value?.click()
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (file) emit('upload-file', file)
  event.target.value = ''
}
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-white/70 bg-white/85 backdrop-blur-xl">
    <div class="mx-auto flex max-w-[1560px] flex-col gap-3 px-4 py-3 sm:px-6 xl:flex-row xl:items-center xl:justify-between lg:px-8">
      <div class="flex items-center gap-3">
        <div class="relative grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 shadow-lg shadow-indigo-500/30">
          <Sparkles class="h-5 w-5 text-white" />
          <span class="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-400"></span>
        </div>
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <h1 class="text-lg font-bold tracking-tight text-slate-900">
              SmartClean
              <span class="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">AI</span>
            </h1>
            <span class="badge-soft bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
              INTERVIEW DEMO
            </span>
          </div>
          <p class="mt-0.5 truncate text-xs text-slate-500">智能游戏数据清洗与分析看板 · 海外休闲游戏运营</p>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition hover:brightness-[0.98]"
          :class="statusMeta.pill"
          :title="backendStatus === 'offline' ? '点击重新检测后端服务' : 'FastAPI 服务状态'"
          @click="emit('retry')"
        >
          <span class="relative flex h-2 w-2">
            <span
              v-if="backendStatus !== 'offline'"
              class="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
              :class="statusMeta.ping"
            ></span>
            <span class="relative inline-flex h-2 w-2 rounded-full" :class="statusMeta.dot"></span>
          </span>
          {{ statusMeta.label }}
          <RefreshCw v-if="backendStatus === 'offline'" class="h-3 w-3" />
        </button>

        <span class="mx-1 hidden h-6 w-px bg-slate-200 sm:block"></span>

        <button
          type="button"
          class="btn-secondary"
          :disabled="loading.load || loading.clean || loading.upload || loading.mapping"
          title="生成 20 条海外休闲游戏运营脏数据"
          @click="emit('load-mock')"
        >
          <Loader2 v-if="loading.load" class="h-4 w-4 animate-spin" />
          <DatabaseZap v-else class="h-4 w-4" />
          <span class="hidden sm:inline">加载游戏运营脏数据</span>
          <span class="sm:hidden">演示数据</span>
        </button>

        <button
          type="button"
          class="btn-secondary"
          :disabled="loading.upload || loading.clean || loading.load || loading.mapping"
          title="支持拖拽或选择 .csv / .xlsx；自动识别表头，缺失字段会弹出映射向导"
          @click="pickFile"
        >
          <Loader2 v-if="loading.upload" class="h-4 w-4 animate-spin" />
          <UploadCloud v-else class="h-4 w-4" />
          <span class="hidden sm:inline">上传本地 CSV / Excel</span>
          <span class="sm:hidden">上传文件</span>
        </button>

        <input
          ref="fileInput"
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          class="hidden"
          @change="onFileChange"
        />

        <button
          type="button"
          class="btn-primary"
          :disabled="!hasData || loading.clean || loading.load || loading.upload || loading.mapping"
          :title="hasData ? '执行缺失填充、去重、异常修正与日期标准化' : '请先加载数据'"
          @click="emit('clean')"
        >
          <Loader2 v-if="loading.clean" class="h-4 w-4 animate-spin" />
          <Wand2 v-else class="h-4 w-4" />
          一键执行 AI 清洗
        </button>

        <button
          type="button"
          class="btn-export"
          :disabled="!hasCleaned || loading.export || loading.clean || loading.mapping"
          :title="hasCleaned ? '下载清洗后的干净 CSV' : '请先完成 AI 清洗'"
          @click="emit('export')"
        >
          <Loader2 v-if="loading.export" class="h-4 w-4 animate-spin" />
          <Download v-else class="h-4 w-4" />
          导出干净 CSV
        </button>
      </div>
    </div>
  </header>
</template>
