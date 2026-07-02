<template>
  <div class="transfer-view">
    <el-card>
      <template #header><span class="card-title">数据传输</span></template>

      <el-tabs v-model="activeTab" class="transfer-tabs">
        <el-tab-pane label="业务数据下载" name="transfer">
          <div class="transfer-layout">
          <el-form :model="form" label-width="100px" inline>
            <el-form-item>
              <el-button :icon="Refresh" @click="resetState">刷新</el-button>
            </el-form-item>
            <el-form-item label="站点">
              <el-select v-model="form.site" placeholder="选择站点" style="width: 160px">
                <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item label="时间类型">
              <el-radio-group v-model="form.period_type">
                <el-radio value="monthly">月度</el-radio>
                <el-radio value="range">时段</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="form.period_type === 'monthly'" label="月份">
              <el-date-picker v-model="form.ym" type="month" format="YYYYMM" value-format="YYYYMM" placeholder="选择月份" />
            </el-form-item>
            <template v-else>
              <el-form-item label="开始日期">
                <el-date-picker v-model="form.date_start" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="开始日期" />
              </el-form-item>
              <el-form-item label="结束日期">
                <el-date-picker v-model="form.date_end" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="结束日期" />
              </el-form-item>
            </template>
            <el-form-item label="原始表">
              <el-checkbox-group v-model="form.tables">
                <el-checkbox value="logs">logs</el-checkbox>
                <el-checkbox value="channels">channels</el-checkbox>
                <el-checkbox value="tokens">tokens</el-checkbox>
                <el-checkbox value="users">users</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
          </el-form>

          <el-divider />

          <el-space wrap>
            <el-button type="primary" :loading="loading.export" :disabled="!form.tables.length || anyRunning" @click="doStep('export')">远程导出</el-button>
            <el-button type="success" :loading="loading.download" :disabled="!form.tables.length || anyRunning" @click="doStep('download')">远程下载</el-button>
            <el-button type="warning" :loading="loading.import_" :disabled="!form.tables.length || anyRunning" @click="doStep('import')">本地导入</el-button>
            <el-button type="info" :loading="loading.fill" :disabled="!hasLogs || anyRunning" @click="doStep('fill')">本地填充</el-button>
            <el-button type="danger" :loading="loading.all" :disabled="!form.tables.length || anyRunning" @click="doAll">一键执行</el-button>
            <el-select v-model="selectedLogTable" placeholder="统计表" style="width: 220px" no-data-text="无统计表">
              <el-option v-for="t in logTableOptions" :key="t" :label="t" :value="t" />
            </el-select>
            <el-button type="warning" :loading="loading.uptcustomer" :disabled="anyRunning || !selectedLogTable" @click="doUptcustomer" title="更新所有站点后执行。">上游关联</el-button>
          </el-space>

          <el-divider />

          <el-steps :active="stepActive" finish-status="success" align-center>
            <el-step title="远程导出" :status="stepStatus(0)" />
            <el-step title="远程下载" :status="stepStatus(1)" />
            <el-step title="本地导入" :status="stepStatus(2)" />
            <el-step v-if="hasLogs" title="本地填充" :status="stepStatus(3)" />
          </el-steps>

          <div v-if="timerLabel" class="timer-bar">
            {{ timerLabel }} 耗时 {{ formatSec(timerElapsed) }}
            <span v-if="timerRunning" class="timer-running"></span>
          </div>

          <div v-if="logs.length" class="log-area log-area-flex">
            <div v-for="(log, i) in logs" :key="i" :class="['log-line', log.success ? 'log-success' : 'log-error']">
              [{{ log.step }}] {{ log.success ? '成功' : '失败' }} {{ log.message || '' }}
            </div>
          </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="SQL导入本地" name="sql">
          <el-form inline>
            <el-form-item label="站点">
              <el-select v-model="sqlSite" placeholder="选择站点" style="width: 160px">
                <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="sqlLoading" @click="triggerSqlImport">选择 SQL 文件</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="远程数据传导" name="conduction" lazy>
          <ConductionPanel />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import api from '../api'
import ConductionPanel from '../components/ConductionPanel.vue'

const STATE_KEY = 'billsum_transfer_state'

const sites = ['ai', 'csp', 'pinova', 'wzg', 'qn', 'digitalcloud', 'wshk']
const activeTab = ref('transfer')

// ── Persistent state ──

const logs = ref([])
const stepActive = ref(-1)
const timerLabel = ref('')
const timerElapsed = ref(0)
const timerRunning = ref(false)
const taskId = ref(null)

let timerStart = 0
let tickInterval = null
let pollTimer = null

const STEP_NAMES = { export: '远程导出', download: '远程下载', import: '本地导入', fill: '本地填充', all: '一键执行', uptcustomer: '上游关联' }

function saveState() {
  const s = {
    logs: logs.value,
    stepActive: stepActive.value,
    timerLabel: timerLabel.value,
    timerElapsed: timerElapsed.value,
    timerRunning: timerRunning.value,
    timerStart,
    taskId: taskId.value,
  }
  localStorage.setItem(STATE_KEY, JSON.stringify(s))
}

function loadState() {
  try {
    const raw = localStorage.getItem(STATE_KEY)
    if (!raw) return
    const s = JSON.parse(raw)
    logs.value = s.logs || []
    stepActive.value = s.stepActive ?? -1
    timerLabel.value = s.timerLabel || ''
    timerElapsed.value = s.timerElapsed || 0
    timerRunning.value = s.timerRunning || false
    taskId.value = s.taskId || null
    timerStart = s.timerStart || 0
  } catch { /* ignore */ }
}

function resetState() {
  logs.value = []
  stepActive.value = -1
  timerLabel.value = ''
  timerElapsed.value = 0
  timerRunning.value = false
  taskId.value = null
  timerStart = 0
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  localStorage.removeItem(STATE_KEY)
}

// ── Timer ──

function startTimer(key) {
  const label = STEP_NAMES[key] || key
  timerLabel.value = label
  timerStart = Date.now()
  timerElapsed.value = 0
  timerRunning.value = true
  ensureTick()
  saveState()
}

function stopTimer() {
  timerRunning.value = false
  timerElapsed.value = timerStart ? Math.floor((Date.now() - timerStart) / 1000) : 0
  saveState()
}

function ensureTick() {
  if (tickInterval) return
  tickInterval = setInterval(() => {
    if (timerRunning.value && timerStart) {
      timerElapsed.value = Math.floor((Date.now() - timerStart) / 1000)
    }
  }, 1000)
}

function formatSec(sec) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

// ── Transfer form ──

function getDefaultMonth() {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth()
  if (m === 0) return `${y - 1}12`
  return `${y}${String(m).padStart(2, '0')}`
}

function getDefaultDateRange() {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  const start = `${y}-${String(m).padStart(2, '0')}-01`
  const yesterday = new Date(now.getTime() - 86400000)
  const end = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`
  return [start, end]
}

const [defaultStart, defaultEnd] = getDefaultDateRange()

const form = reactive({
  site: 'wzg',
  period_type: 'monthly',
  ym: getDefaultMonth(),
  date_start: defaultStart,
  date_end: defaultEnd,
  tables: ['logs'],
})

const hasLogs = computed(() => form.tables.includes('logs'))
const anyRunning = computed(() => loading.all || loading.export || loading.download || loading.import_ || loading.fill || loading.uptcustomer)

// ── Log table selector for uptcustomer ──

const selectedLogTable = ref('')
const logTableOptions = ref([])

async function loadLogTables() {
  try {
    const { data } = await api.query.tables(form.site, 'output')
    const tables = (data.tables || []).map(t => t.name).filter(n => n.startsWith('logs') && !n.endsWith('orig'))
    logTableOptions.value = tables
    if (tables.length && !tables.includes(selectedLogTable.value)) {
      selectedLogTable.value = tables[tables.length - 1]
    } else if (!tables.length) {
      selectedLogTable.value = ''
    }
  } catch { /* ignore */ }
}

watch(() => form.site, () => {
  selectedLogTable.value = ''
  logTableOptions.value = []
  loadLogTables()
})

const loading = reactive({
  export: false,
  download: false,
  import_: false,
  fill: false,
  all: false,
  uptcustomer: false,
})

function addLog(step, success, message = '') {
  logs.value.push({ step, success, message })
}

function stepStatus(index) {
  if (index < stepActive.value) return 'success'
  if (index === stepActive.value) return 'process'
  return 'wait'
}

function getPayload() {
  return {
    site: form.site,
    period_type: form.period_type,
    ym: form.period_type === 'monthly' ? form.ym : '',
    date_start: form.period_type === 'range' ? form.date_start : '',
    date_end: form.period_type === 'range' ? form.date_end : '',
    tables: form.tables,
  }
}

async function doStep(step) {
  const label = STEP_NAMES[step] || step
  try {
    await ElMessageBox.confirm(`确认执行"${label}"？`, '操作确认', { confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  const lk = step === 'import' ? 'import_' : step
  loading[lk] = true
  logs.value = []
  stepActive.value = -1
  startTimer(step)
  try {
    const { data } = await api.transfer[step](getPayload())
    const countInfo = data.count != null ? `（${data.count} 条记录）` : ''
    addLog(data.step || step, data.success, data.error || (data.log_name || '') + countInfo)
    stepActive.value = 0
    ElMessage.success((data.step || step) + ' 完成')
    if (data.log_name) refreshLogTableSelector(data.log_name)
  } catch (e) {
    addLog(step, false, e.response?.data?.detail || e.message)
    stepActive.value = 0
    ElMessage.error(step + ' 失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading[lk] = false
    stopTimer()
  }
}

// ── 上游关联 ──

function refreshLogTableSelector(newTableName) {
  if (newTableName && !newTableName.endsWith('orig') && !logTableOptions.value.includes(newTableName)) {
    logTableOptions.value.push(newTableName)
  }
  if (newTableName && !newTableName.endsWith('orig')) {
    selectedLogTable.value = newTableName
  }
}

async function doUptcustomer() {
  if (!selectedLogTable.value) {
    ElMessage.warning('请先选择统计表')
    return
  }
  try {
    await ElMessageBox.confirm(`确认执行"上游关联"？将对表 ${selectedLogTable.value} 同步上下游客户折扣信息。\n\n提示：请确保所有站点已更新数据后再执行。`, '操作确认', { confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  loading.uptcustomer = true
  logs.value = []
  stepActive.value = -1
  startTimer('uptcustomer')
  try {
    const { data } = await api.transfer.uptcustomer({ ...getPayload(), table_name: selectedLogTable.value })
    addLog('uptcustomer', data.success, data.log_name || '')
    if (data.details) {
      for (const d of data.details) addLog('uptcustomer', true, d)
    }
    stepActive.value = 0
    ElMessage.success('上游关联完成')
  } catch (e) {
    addLog('uptcustomer', false, e.response?.data?.detail || e.message)
    stepActive.value = 0
    ElMessage.error('上游关联失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.uptcustomer = false
    stopTimer()
  }
}

// ── Async "一键执行" ──

async function doAll() {
  try {
    await ElMessageBox.confirm('确认执行"一键执行"？将依次执行远程导出、远程下载、本地导入、本地填充。', '操作确认', { confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  loading.all = true
  logs.value = []
  stepActive.value = -1
  startTimer('all')
  try {
    const { data } = await api.transfer.asyncAll(getPayload())
    taskId.value = data.task_id
    saveState()
    pollTask(data.task_id)
  } catch (e) {
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
    loading.all = false
    stopTimer()
  }
}

function pollTask(id) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const { data } = await api.transfer.taskStatus(id)
      if (data.status === 'done') {
        clearInterval(pollTimer)
        pollTimer = null
        loading.all = false
        taskId.value = null
        stopTimer()
        showResults(data.results)
      }
    } catch { /* keep polling */ }
  }, 3000)
}

function showResults(results) {
  let failed = false
  let newTableName = ''
  for (let i = 0; i < results.length; i++) {
    const r = results[i]
    const cnt = r.count != null ? `（${r.count} 条记录）` : ''
    addLog(r.step, r.success, r.error || (r.log_name || '') + cnt)
    stepActive.value = i
    if (r.log_name) newTableName = r.log_name
    if (!r.success) { failed = true; break }
  }
  if (!failed) stepActive.value = results.length
  if (!failed && newTableName) refreshLogTableSelector(newTableName)
  saveState()
  if (failed) {
    ElMessage.error('执行失败，请查看日志')
  } else {
    ElMessage.success('一键执行完成')
  }
}

// ── Lifecycle ──

onMounted(() => {
  loadState()
  ensureTick()
  loadLogTables()
  // resume polling if async task was running
  if (taskId.value && timerRunning.value) {
    loading.all = true
    pollTask(taskId.value)
  }
})

onUnmounted(() => {
  if (tickInterval) { clearInterval(tickInterval); tickInterval = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
})

// ── SQL import tab ──

const sqlSite = ref('wzg')
const sqlLoading = ref(false)

function triggerSqlImport() {
  if (!sqlSite.value) {
    ElMessage.warning('请先选择站点')
    return
  }
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.sql'
  input.onchange = (e) => {
    const file = e.target.files?.[0]
    if (file) doSqlImport(file)
  }
  input.click()
}

async function doSqlImport(file) {
  const db_name = `sum_${sqlSite.value}`
  try {
    await ElMessageBox.confirm(
      `确认将 SQL 文件 "${file.name}" 导入到站点 "${sqlSite.value}"（数据库 ${db_name}）？`,
      'SQL 导入确认',
      { confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  sqlLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await api.system.executeSql(sqlSite.value, formData)
    ElMessage.success('SQL 文件执行成功')
  } catch (e) {
    ElMessage.error('SQL 执行失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    sqlLoading.value = false
  }
}
</script>

<style scoped>
.transfer-view { width: 100%; }
.card-title { font-size: 16px; font-weight: bold; }
.transfer-tabs { height: 100%; display: flex; flex-direction: column; }
.transfer-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: hidden; }
.transfer-tabs :deep(.el-tab-pane) { height: 100%; }
.transfer-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.timer-bar {
  text-align: center;
  margin-top: 12px;
  font-family: Consolas, monospace;
  font-size: 14px;
  color: #606266;
}
.timer-running {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #67c23a;
  margin-left: 6px;
  vertical-align: middle;
  animation: blink 1s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.log-area { margin-top: 12px; background: #1e1e1e; padding: 12px; border-radius: 4px; max-height: 300px; overflow-y: auto; }
.log-area-flex { flex: 1; min-height: 0; max-height: none; }
.log-line { font-family: Consolas, monospace; font-size: 13px; line-height: 1.8; }
.log-success { color: #67c23a; }
.log-error { color: #f56c6c; }
</style>
