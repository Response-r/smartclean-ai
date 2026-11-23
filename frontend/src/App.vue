<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CloudOff,
  DatabaseZap,
  FileSpreadsheet,
  Info,
  Loader2,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import TopBar from './components/TopBar.vue'
import MetricCards from './components/MetricCards.vue'
import InsightPanel from './components/InsightPanel.vue'
import DataTable from './components/DataTable.vue'
import TerminalLog from './components/TerminalLog.vue'
import ColumnMappingModal from './components/ColumnMappingModal.vue'
import {
  cleanDataset,
  confirmUpload,
  downloadCleanedCsv,
  fetchHealth,
  generateMockData,
  inspectUpload,
} from './api'
import { COLUMN_ORDER, FIELD_META, formatNumber } from './constants'

const datasetId = ref('')
const datasetSource = ref('')
const datasetLabel = ref('')
const columns = ref([])
const rawRows = ref([])
const rawFlags = ref([])
const rawTotal = ref(0)
const rawIssueCells = ref(0)
const rawHealth = ref(0)

const cleanedRows = ref([])
const cleanedFlags = ref([])
const cleanTotal = ref(0)
const metrics = ref(null)
const insights = ref([])

const logs = ref([])
const loadLogs = ref([])
const backendStatus = ref('checking')
const mappingSummary = ref(null)

const busy = reactive({ load: false, upload: false, clean: false, export: false, mapping: false })
const errorDialog = reactive({ open: false, title: '', message: '', showRetry: false })
const mappingState = reactive({ open: false, inspection: null, confirming: false })
const toast = reactive({ show: false, text: '', type: 'success' })
const dragging = ref(false)

let toastTimer = null
let dragDepth = 0

const hasData = computed(() => Boolean(datasetId.value))
const hasCleaned = computed(() => Boolean(metrics.value))
const preview = computed(() => ({
  total: rawTotal.value,
  issue_cells: rawIssueCells.value,
  health: rawHealth.value,
}))
const datasetShortId = computed(() =>
  datasetId.value ? datasetId.value.slice(0, 8).toUpperCase() : '--------',
)
const sourceLabel = computed(() => {
  if (!hasData.value) return '尚未载入数据'
  return datasetSource.value === 'mock' ? '演示数据' : '本地文件'
})

function showToast(text, type = 'success') {
  toast.text = text
  toast.type = type
  toast.show = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.show = false
  }, 3600)
}

function showError(title, message, showRetry = false) {
  errorDialog.title = title
  errorDialog.message = message
  errorDialog.showRetry = showRetry
  errorDialog.open = true
}

function closeError() {
  errorDialog.open = false
}

function handleNetworkError(error) {
  if (error?.message?.startsWith('无法连接后端服务')) {
    backendStatus.value = 'offline'
  }
}

function applyPreview(payload, label) {
  datasetId.value = payload.dataset_id
  datasetSource.value = payload.source || ''
  datasetLabel.value = payload.filename || label
  columns.value = payload.columns || []
  rawRows.value = payload.raw?.rows || []
  rawFlags.value = payload.raw?.flags || []
  rawTotal.value = payload.raw?.total || 0
  rawIssueCells.value = payload.raw?.issue_cells || 0
  rawHealth.value = payload.raw?.health || 0
  mappingSummary.value = payload.mapping_summary || null

  cleanedRows.value = []
  cleanedFlags.value = []
  cleanTotal.value = 0
  metrics.value = null
  insights.value = []

  loadLogs.value = payload.logs || []
  logs.value = [...loadLogs.value]
}

async function loadMock() {
  if (busy.load || busy.upload || busy.clean || busy.mapping) return
  busy.load = true
  try {
    const payload = await generateMockData()
    applyPreview(payload, '游戏运营演示脏数据')
    backendStatus.value = 'online'
    showToast(`已载入 ${payload.raw.total} 条演示脏数据，点击「一键执行 AI 清洗」开始诊断`)
  } catch (error) {
    handleNetworkError(error)
    showError('加载演示数据失败', error.message)
  } finally {
    busy.load = false
  }
}

async function handleFile(file) {
  if (!file) return
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!['.csv', '.xlsx'].includes(extension)) {
    showError('文件格式不支持', '请上传 .csv 或 .xlsx 格式的文件。')
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    showError('文件超过 10MB', '请拆分文件后再上传，或使用演示数据体验完整流程。')
    return
  }
  if (busy.upload || busy.load || busy.clean || busy.mapping) return

  busy.upload = true
  try {
    const inspection = await inspectUpload(file)
    backendStatus.value = 'online'
    const suggested = inspection.suggested_mapping || {}
    const autoComplete = COLUMN_ORDER.every((field) => Boolean(suggested[field]))

    if (autoComplete) {
      const payload = await confirmUpload(inspection.pending_id, suggested)
      applyPreview(payload, file.name)
      showToast(`文件「${file.name}」已自动识别 7 个字段，共 ${payload.raw.total} 行`)
    } else {
      mappingState.inspection = inspection
      mappingState.open = true
      busy.mapping = true
    }
  } catch (error) {
    handleNetworkError(error)
    showError('文件解析 / 自动映射失败', error.message)
  } finally {
    busy.upload = false
  }
}

function closeMapping() {
  if (mappingState.confirming) return
  mappingState.open = false
  mappingState.inspection = null
  busy.mapping = false
}

async function confirmMapping(mapping) {
  const inspection = mappingState.inspection
  if (!inspection) return
  mappingState.confirming = true
  busy.mapping = true
  try {
    const payload = await confirmUpload(inspection.pending_id, mapping)
    applyPreview(payload, inspection.filename)
    const defaultCount = payload.mapping_summary?.default_fields?.length || 0
    mappingState.open = false
    mappingState.inspection = null
    showToast(
      defaultCount
        ? `文件已载入，其中 ${defaultCount} 个字段使用默认值，业务洞察可能失真`
        : `文件「${inspection.filename}」字段映射完成，共 ${payload.raw.total} 行`,
      defaultCount ? 'info' : 'success',
    )
  } catch (error) {
    handleNetworkError(error)
    showError('字段映射导入失败', error.message)
  } finally {
    mappingState.confirming = false
    busy.mapping = false
  }
}

async function runClean() {
  if (busy.clean || busy.load || busy.upload || busy.mapping) return
  if (!hasData.value) {
    showError('还没有可清洗的数据', '请先点击「加载游戏运营脏数据」，或上传本地 CSV / Excel 文件。')
    return
  }

  busy.clean = true
  try {
    const result = await cleanDataset(datasetId.value)
    cleanedRows.value = result.rows || []
    cleanedFlags.value = result.flags || []
    cleanTotal.value = result.total || 0
    metrics.value = result.metrics
    insights.value = result.insights || []
    logs.value = [
      ...loadLogs.value,
      {
        step: '清洗任务',
        message: `开始处理 ${datasetLabel.value} · 数据集 ${datasetShortId.value}`,
        ms: 0,
        level: 'info',
      },
      ...(result.logs || []),
    ]
    backendStatus.value = 'online'
    showToast(
      `AI 清洗完成：${result.metrics.raw_total} → ${result.metrics.clean_total} 条，健康度 ${result.metrics.raw_health} → ${result.metrics.clean_health}`,
    )
  } catch (error) {
    handleNetworkError(error)
    showError('AI 清洗失败', error.message)
  } finally {
    busy.clean = false
  }
}

async function exportCsv() {
  if (!hasCleaned.value) {
    showError('暂无可导出的数据', '请先执行 AI 清洗，导出按钮会在清洗完成后自动可用。')
    return
  }
  if (busy.export || busy.clean || busy.mapping) return

  busy.export = true
  try {
    const blob = await downloadCleanedCsv(datasetId.value)
    const fileBlob =
      blob instanceof Blob ? blob : new Blob([blob], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(fileBlob)
    const link = document.createElement('a')
    const stamp = new Date()
      .toISOString()
      .slice(0, 19)
      .replace(/[:T]/g, '')
    link.href = url
    link.download = `smartclean_cleaned_${stamp}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    showToast('清洗后 CSV 已开始下载')
  } catch (error) {
    handleNetworkError(error)
    showError('导出失败', error.message)
  } finally {
    busy.export = false
  }
}

async function checkBackend({ autoLoad = true } = {}) {
  backendStatus.value = 'checking'
  try {
    await fetchHealth()
    backendStatus.value = 'online'
    if (autoLoad && !hasData.value) await loadMock()
  } catch (error) {
    backendStatus.value = 'offline'
    showError(
      '后端服务未连接',
      '请按以下步骤启动后端：\n1. 双击项目根目录的 start_backend.bat\n2. 等待终端出现 Uvicorn running on http://127.0.0.1:8000\n3. 点击下方「重新检测」\n\n前端界面已正常加载，所有数据仅在本机处理。',
      true,
    )
  }
}

function dialogRetry() {
  closeError()
  checkBackend({ autoLoad: !hasData.value })
}

function onDragEnter(event) {
  if (!event.dataTransfer?.types?.includes('Files')) return
  dragDepth += 1
  dragging.value = true
}

function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) dragging.value = false
}

function onDrop(event) {
  dragDepth = 0
  dragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) handleFile(file)
}

function preventWindowDrop(event) {
  event.preventDefault()
}

function onKeydown(event) {
  if (event.key !== 'Escape') return
  if (errorDialog.open) {
    closeError()
    return
  }
  if (mappingState.open) closeMapping()
}

onMounted(() => {
  window.addEventListener('dragover', preventWindowDrop)
  window.addEventListener('drop', preventWindowDrop)
  window.addEventListener('keydown', onKeydown)
  checkBackend()
})

onBeforeUnmount(() => {
  window.removeEventListener('dragover', preventWindowDrop)
  window.removeEventListener('drop', preventWindowDrop)
  window.removeEventListener('keydown', onKeydown)
  clearTimeout(toastTimer)
})
</script>

<template>
  <div
    class="relative min-h-screen overflow-x-hidden"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <div class="pointer-events-none fixed inset-0 -z-20 overflow-hidden">
      <div class="absolute -left-32 -top-40 h-[460px] w-[460px] animate-float rounded-full bg-indigo-300/25 blur-3xl"></div>
      <div class="absolute -right-40 top-1/3 h-[500px] w-[500px] rounded-full bg-fuchsia-300/20 blur-3xl"></div>
      <div class="absolute bottom-0 left-1/3 h-[380px] w-[380px] rounded-full bg-emerald-200/20 blur-3xl"></div>
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.06),_transparent_55%)]"></div>
    </div>

    <TopBar
      :has-data="hasData"
      :has-cleaned="hasCleaned"
      :backend-status="backendStatus"
      :loading="busy"
      @load-mock="loadMock"
      @upload-file="handleFile"
      @clean="runClean"
      @export="exportCsv"
      @retry="checkBackend({ autoLoad: !hasData })"
    />

    <main class="mx-auto max-w-[1560px] space-y-5 px-4 py-5 sm:px-6 lg:px-8 lg:py-6">
      <div
        v-if="backendStatus !== 'online'"
        class="flex flex-col gap-3 rounded-2xl border px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
        :class="
          backendStatus === 'offline'
            ? 'border-rose-200 bg-rose-50/80'
            : 'border-amber-200 bg-amber-50/80'
        "
      >
        <div class="flex items-start gap-3">
          <span
            class="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg"
            :class="
              backendStatus === 'offline'
                ? 'bg-rose-100 text-rose-600'
                : 'bg-amber-100 text-amber-600'
            "
          >
            <CloudOff v-if="backendStatus === 'offline'" class="h-4 w-4" />
            <Loader2 v-else class="h-4 w-4 animate-spin" />
          </span>
          <div>
            <p
              class="text-xs font-semibold"
              :class="backendStatus === 'offline' ? 'text-rose-700' : 'text-amber-700'"
            >
              {{ backendStatus === 'offline' ? '后端服务未连接' : '正在检测后端服务…' }}
            </p>
            <p class="mt-0.5 text-[11px] leading-5 text-slate-500">
              {{
                backendStatus === 'offline'
                  ? '请先双击项目根目录的 start_backend.bat 启动 FastAPI（http://127.0.0.1:8000），再点击右侧重新连接。'
                  : '正在通过 Vite 代理 /api 探测 FastAPI 健康状态'
              }}
            </p>
          </div>
        </div>
        <button
          v-if="backendStatus === 'offline'"
          type="button"
          class="btn-secondary shrink-0 !py-2 text-xs"
          @click="checkBackend({ autoLoad: !hasData })"
        >
          <RefreshCw class="h-3.5 w-3.5" />
          重新连接
        </button>
      </div>

      <section class="panel flex flex-col gap-4 px-4 py-3.5 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div class="flex items-center gap-2.5">
            <div class="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-500">
              <FileSpreadsheet class="h-4 w-4" />
            </div>
            <div>
              <p class="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Current Dataset
              </p>
              <p class="max-w-[260px] truncate text-xs font-semibold text-slate-700">
                {{ datasetLabel || '尚未载入数据' }}
              </p>
            </div>
          </div>
          <span class="badge-soft bg-slate-100 font-mono text-slate-500">DS · {{ datasetShortId }}</span>
          <span class="badge-soft bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
            {{ sourceLabel }}
          </span>
          <span
            v-if="mappingSummary?.default_fields?.length"
            class="badge-soft bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-100"
            :title="`默认值字段：${mappingSummary.default_fields.map((field) => FIELD_META[field]?.label || field).join('、')}`"
          >
            默认值填充 {{ mappingSummary.default_fields.length }} 字段
          </span>
          <span class="text-[11px] text-slate-400">
            原始 <b class="font-semibold text-slate-600">{{ formatNumber(rawTotal) }}</b> 条
          </span>
          <template v-if="metrics">
            <ChevronRight class="h-3.5 w-3.5 text-slate-300" />
            <span class="text-[11px] text-slate-400">
              清洗后 <b class="font-semibold text-emerald-600">{{ formatNumber(cleanTotal) }}</b> 条
            </span>
            <span class="badge-soft bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-100">
              健康度 {{ metrics.clean_health }}
            </span>
          </template>
        </div>

        <div class="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold">
          <div class="flex items-center gap-1.5" :class="hasData ? 'text-indigo-600' : 'text-slate-400'">
            <span
              class="grid h-5 w-5 place-items-center rounded-full text-[9px]"
              :class="hasData ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/30' : 'bg-slate-100 text-slate-400'"
            >
              1
            </span>
            载入数据
          </div>
          <ChevronRight class="h-3 w-3 text-slate-300" />
          <div class="flex items-center gap-1.5" :class="hasCleaned ? 'text-indigo-600' : 'text-slate-400'">
            <span
              class="grid h-5 w-5 place-items-center rounded-full text-[9px]"
              :class="hasCleaned ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/30' : 'bg-slate-100 text-slate-400'"
            >
              2
            </span>
            AI 清洗
          </div>
          <ChevronRight class="h-3 w-3 text-slate-300" />
          <div class="flex items-center gap-1.5" :class="hasCleaned ? 'text-emerald-600' : 'text-slate-400'">
            <span
              class="grid h-5 w-5 place-items-center rounded-full text-[9px]"
              :class="hasCleaned ? 'bg-emerald-500 text-white shadow-sm shadow-emerald-500/30' : 'bg-slate-100 text-slate-400'"
            >
              3
            </span>
            导出 CSV
          </div>
        </div>
      </section>

      <MetricCards
        :metrics="metrics"
        :preview="preview"
        :loading="busy.load || busy.upload || busy.clean"
      />

      <InsightPanel :insights="insights" :loading="busy.clean" />

      <div class="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <DataTable
          variant="raw"
          title="原始脏数据"
          subtitle="缺失 / 重复 / 异常值浅红高亮，悬停角标查看诊断原因"
          :columns="columns"
          :rows="rawRows"
          :flags="rawFlags"
          :loading="busy.load || busy.upload"
          empty-title="尚未载入原始数据"
          empty-hint="点击顶部「加载游戏运营脏数据」，或直接把 CSV / Excel 文件拖拽到页面"
        />
        <DataTable
          variant="clean"
          title="清洗后干净数据"
          subtitle="绿色角标标识被 AI 修复的单元格，可一键导出"
          :columns="columns"
          :rows="cleanedRows"
          :flags="cleanedFlags"
          :loading="busy.clean"
          empty-title="等待 AI 清洗结果"
          empty-hint="点击顶部「一键执行 AI 清洗」，Pandas 将自动完成缺失填充、去重、异常修正与日期标准化"
        />
      </div>

      <TerminalLog :logs="logs" :running="busy.clean" />

      <footer class="flex flex-col items-center justify-between gap-2 border-t border-slate-200/70 pb-2 pt-5 text-[11px] text-slate-400 sm:flex-row">
        <p class="inline-flex items-center gap-1.5">
          <DatabaseZap class="h-3.5 w-3.5 text-indigo-400" />
          SmartClean AI · FastAPI + Pandas + OpenPyXL · Vue 3 + Vite + Tailwind CSS
        </p>
        <p class="inline-flex items-center gap-1.5">
          <ShieldCheck class="h-3.5 w-3.5 text-emerald-500" />
          内置规则引擎 · 数据不出本机
        </p>
      </footer>
    </main>

    <Transition name="fade">
      <div
        v-if="dragging"
        class="pointer-events-none fixed inset-0 z-[60] flex items-center justify-center bg-indigo-950/40 p-6 backdrop-blur-sm"
      >
        <div class="w-full max-w-lg rounded-3xl border-2 border-dashed border-white/70 bg-white/10 px-8 py-12 text-center shadow-2xl">
          <div class="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-white/15 text-white ring-1 ring-white/30">
            <UploadCloud class="h-8 w-8" />
          </div>
          <p class="mt-5 text-xl font-bold text-white">释放文件，开始智能清洗</p>
          <p class="mt-1.5 text-sm text-indigo-100">支持 .csv / .xlsx · 单文件最大 10MB</p>
        </div>
      </div>
    </Transition>

    <ColumnMappingModal
      :open="mappingState.open"
      :inspection="mappingState.inspection"
      :confirming="mappingState.confirming"
      @confirm="confirmMapping"
      @cancel="closeMapping"
    />

    <Transition name="fade">
      <div
        v-if="errorDialog.open"
        class="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm"
        @click.self="closeError"
      >
        <div class="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
          <div class="flex items-start gap-3 p-5">
            <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-rose-50 text-rose-600">
              <AlertTriangle class="h-5 w-5" />
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="text-sm font-bold text-slate-900">{{ errorDialog.title }}</h3>
              <p class="thin-scrollbar mt-2 max-h-60 overflow-y-auto whitespace-pre-line pr-1 text-xs leading-6 text-slate-500">{{ errorDialog.message }}</p>
            </div>
            <button
              type="button"
              class="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              aria-label="关闭"
              @click="closeError"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
          <div class="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/70 px-5 py-3">
            <button type="button" class="btn-secondary !py-2 text-xs" @click="closeError">我知道了</button>
            <button
              v-if="errorDialog.showRetry"
              type="button"
              class="btn-primary !py-2 text-xs"
              @click="dialogRetry"
            >
              <RefreshCw class="h-3.5 w-3.5" />
              重新检测
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="toast">
      <div
        v-if="toast.show"
        class="fixed bottom-5 right-5 z-[80] flex max-w-md items-start gap-2.5 rounded-xl border bg-white/95 px-4 py-3 shadow-xl backdrop-blur"
        :class="toast.type === 'error' ? 'border-rose-200' : 'border-emerald-200'"
      >
        <span
          class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg"
          :class="toast.type === 'error' ? 'bg-rose-50 text-rose-600' : 'bg-emerald-50 text-emerald-600'"
        >
          <AlertTriangle v-if="toast.type === 'error'" class="h-4 w-4" />
          <Info v-else-if="toast.type === 'info'" class="h-4 w-4" />
          <CheckCircle2 v-else class="h-4 w-4" />
        </span>
        <p class="pt-0.5 text-xs leading-5 text-slate-600">{{ toast.text }}</p>
        <button
          type="button"
          class="ml-1 rounded-md p-0.5 text-slate-300 transition hover:bg-slate-100 hover:text-slate-500"
          aria-label="关闭提示"
          @click="toast.show = false"
        >
          <X class="h-3.5 w-3.5" />
        </button>
      </div>
    </Transition>
  </div>
</template>
