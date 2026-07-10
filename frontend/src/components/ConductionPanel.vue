<template>
  <div class="conduction-panel">
    <div class="group-bar">
      <span class="group-label">参数组配置</span>
      <el-select
        :model-value="selectedName"
        @change="onSelectGroup"
        style="width: 480px"
        placeholder="选择配置组"
      >
        <el-option v-for="g in groups" :key="g.name" :label="g.name" :value="g.name" />
      </el-select>
      <el-button v-if="!isDefaultSelected && selectedName" type="danger" plain size="small" :icon="Delete" :loading="deleting" @click="deleteGroup">删除</el-button>
    </div>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span class="ep-title">源库</span></template>
          <ConductionEndpointForm which="source" :endpoint="config.source" @tables="onSourceTables" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span class="ep-title">目的库</span></template>
          <ConductionEndpointForm which="dest" :endpoint="config.destination" />
        </el-card>
      </el-col>
    </el-row>

    <el-divider />

    <el-space wrap>
      <el-button type="success" :icon="Files" @click="openTableDialog">表名选择…</el-button>
      <el-tag :type="modeTag" effect="plain">{{ modeHint }}</el-tag>
      <el-checkbox v-model="addNew" :disabled="isDefaultSelected">新增</el-checkbox>
      <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
      <el-button :loading="resetting" @click="resetConfig">重置配置</el-button>
      <el-checkbox v-model="skipImport" :disabled="running" style="margin-left: 8px">导入目的库</el-checkbox>
      <el-button type="danger" :disabled="running" :loading="starting" @click="startTransfer">开始传导</el-button>
      <el-button v-if="taskDone && hasTgz" type="primary" :icon="Download" plain @click="downloadTgz">下载 {{ downloadName }}</el-button>
    </el-space>

    <div v-if="timerRunning || elapsed" class="timer-bar">
      传导耗时 {{ formatSec(elapsed) }}
      <span v-if="timerRunning" class="timer-running"></span>
    </div>

    <div v-if="logs.length" class="log-area">
      <div v-for="(l, i) in logs" :key="i" :class="['log-line', l.success ? 'log-success' : 'log-error']">
        <span class="log-ts">{{ l.ts }}</span>
        <span class="log-step">[{{ l.step }}]</span>
        {{ l.success ? '✓' : '✗' }} {{ l.message }}
      </div>
    </div>

    <ConductionTableSelect
      v-model="tableDialog"
      :tables="sourceTables"
      :selected="config.source.selected_tables"
      :loading="tablesLoading"
      @update:selected="config.source.selected_tables = $event"
      @refresh="refreshSourceTables"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Files, Download, Delete } from '@element-plus/icons-vue'
import api from '../api'
import ConductionEndpointForm from './ConductionEndpointForm.vue'
import ConductionTableSelect from './ConductionTableSelect.vue'

const DEFAULT_GROUP_NAME = '默认配置'

function defaultEndpoint(over) {
  return {
    deploy_type: 'local', run_mode: 'docker', os_type: 'windows',
    ssh: { auth_method: 'key', password: '', key_path: '', user: 'root', host: '', port: 22, remote_path: '' },
    db: { user: 'root', password: '', db_name: 'shadow_manager', container_name: '', host: '', port: 3306 },
    selected_tables: [], all_checked: false,
    ...over,
  }
}

// current editable endpoints (loaded from the selected group)
const config = reactive({
  source: defaultEndpoint({
    deploy_type: 'remote', run_mode: 'docker', os_type: 'linux',
    ssh: { auth_method: 'key', password: '', key_path: '/app/data/ssh_keys/host20260311', user: 'root', host: 'shadowdev.burncloud.cn', port: 22, remote_path: '~/data/' },
    db: { user: 'root', password: 'burncloud123456qwe', db_name: 'shadow_manager', container_name: 'shadow-manager-dev-mysql', host: 'localhost', port: 3306 },
  }),
  destination: defaultEndpoint({ deploy_type: 'local', run_mode: 'host', os_type: 'windows', db: { user: 'root', password: '123456', db_name: 'shadow_manager', container_name: '', host: '172.20.0.3', port: 3306 } }),
})

// config groups + selection
const groups = ref([])
const selectedName = ref('')
const addNew = ref(false)
const isDefaultSelected = computed(() => selectedName.value === DEFAULT_GROUP_NAME)

// when the default group becomes selected, lock the 新增 checkbox (checked+disabled)
watch(isDefaultSelected, (d) => {
  if (d) addNew.value = true
}, { immediate: true })

const sourceTables = ref([])
const tableDialog = ref(false)
const tablesLoading = ref(false)

const saving = ref(false)
const resetting = ref(false)
const deleting = ref(false)
const starting = ref(false)
const running = ref(false)
const taskId = ref(null)
const hasTgz = ref(false)
const downloadName = ref('')
const taskDone = ref(false)
const skipImport = ref(true)
const logs = ref([])
const elapsed = ref(0)
const timerRunning = ref(false)
let timerStart = 0
let tickInterval = null
let pollTimer = null

const modeHint = computed(() => {
  const s = config.source
  const all = s.all_checked || (sourceTables.value.length > 0
    && sourceTables.value.every(t => s.selected_tables.includes(t)))
  if (all) return '整库备份模式'
  return s.selected_tables.length ? `选择备份：${s.selected_tables.length} 张表` : '未选择表'
})
const modeTag = computed(() => {
  const s = config.source
  const all = s.all_checked || (sourceTables.value.length > 0
    && sourceTables.value.every(t => s.selected_tables.includes(t)))
  if (all) return 'success'
  return s.selected_tables.length ? 'warning' : 'info'
})

// ── group naming (mirrors backend group_name) ──
function hostSegment(ep) {
  if (ep.deploy_type === 'local') return 'localhost'
  const h = (ep.ssh?.host || '').trim()
  if (!h) return 'remote'
  return h.split('.')[0]
}
function groupName(src, dst) {
  return `${hostSegment(src)}:${src.db.db_name} → ${hostSegment(dst)}:${dst.db.db_name}`
}

function patchEndpoint(target, src) {
  if (!src) return
  target.deploy_type = src.deploy_type ?? target.deploy_type
  target.run_mode = src.run_mode ?? target.run_mode
  target.os_type = src.os_type ?? target.os_type
  target.selected_tables = Array.isArray(src.selected_tables) ? src.selected_tables : target.selected_tables
  target.all_checked = typeof src.all_checked === 'boolean' ? src.all_checked : target.all_checked
  if (src.ssh) target.ssh = { ...target.ssh, ...src.ssh }
  if (src.db) target.db = { ...target.db, ...src.db }
}

function loadGroupIntoForm(name) {
  const g = groups.value.find(x => x.name === name)
  if (!g) return
  patchEndpoint(config.source, g.source)
  patchEndpoint(config.destination, g.destination)
}

function onSelectGroup(name) {
  selectedName.value = name
  loadGroupIntoForm(name)
  sourceTables.value = []
  // req 5: default → 新增 locked (checked+disabled); otherwise revert to unchecked
  addNew.value = (name === DEFAULT_GROUP_NAME)
}

async function deleteGroup() {
  if (isDefaultSelected.value || !selectedName.value) return
  try {
    await ElMessageBox.confirm(`确定删除配置组「${selectedName.value}」？`, '删除配置组',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  deleting.value = true
  try {
    const newGroups = groups.value.filter(g => g.name !== selectedName.value)
    await api.conduction.saveConfig({ groups: newGroups, selected: DEFAULT_GROUP_NAME })
    groups.value = newGroups
    onSelectGroup(DEFAULT_GROUP_NAME)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    deleting.value = false
  }
}

function onSourceTables(tables) {
  sourceTables.value = tables || []
}

async function refreshSourceTables() {
  tablesLoading.value = true
  try {
    const { data } = await api.conduction.refreshTables(config.source)
    if (data.success) {
      sourceTables.value = data.tables || []
      ElMessage.success(`已获取 ${sourceTables.value.length} 张表`)
    } else {
      ElMessage.error(data.message || '获取表名失败')
    }
  } catch (e) {
    ElMessage.error('获取表名失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    tablesLoading.value = false
  }
}

async function openTableDialog() {
  if (running.value) { running.value = false; stopTimer() }
  if (!sourceTables.value.length) await refreshSourceTables()
  tableDialog.value = true
}

async function saveConfig() {
  if (running.value) { running.value = false; stopTimer() }
  saving.value = true
  try {
    const src = JSON.parse(JSON.stringify(config.source))
    const dst = JSON.parse(JSON.stringify(config.destination))
    const newGroups = groups.value.map(g => ({ name: g.name, source: g.source, destination: g.destination }))
    if (addNew.value) {
      // req 4: 新增 → create a new named group
      const rand = String(Math.floor(Math.random() * 900) + 100)
      const base = `${groupName(src, dst)}:${rand}`
      let name = base, n = 2
      while (newGroups.some(g => g.name === name)) { name = `${base} (${n})`; n++ }
      newGroups.push({ name, source: src, destination: dst })
      selectedName.value = name
    } else {
      // req 4: not 新增 → update the selected group (default is locked to 新增, so never here for default)
      const idx = newGroups.findIndex(g => g.name === selectedName.value)
      if (idx < 0) {
        ElMessage.error('未找到当前配置组')
        return
      }
      newGroups[idx] = { name: newGroups[idx].name, source: src, destination: dst }
    }
    await api.conduction.saveConfig({ groups: newGroups, selected: selectedName.value })
    groups.value = newGroups
    loadGroupIntoForm(selectedName.value)
    ElMessage.success('配置已保存')
    // req 7: after save, 新增 reverts to unchecked (re-lock if default selected)
    addNew.value = (selectedName.value === DEFAULT_GROUP_NAME)
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function resetConfig() {
  try {
    await ElMessageBox.confirm('确定放弃当前未保存的修改，恢复到最后保存的配置？', '重置配置',
      { confirmButtonText: '重置', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  if (running.value) { running.value = false; stopTimer() }
  resetting.value = true
  try {
    selectedName.value = ''   // force loadServerConfig to pick the server-side selected group
    await loadServerConfig()
    sourceTables.value = []
    ElMessage.success('已恢复到最后保存的配置')
  } catch (e) {
    ElMessage.error('重置失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    resetting.value = false
  }
}

async function startTransfer() {
  try {
    await ElMessageBox.confirm('确认开始数据传导？默认会覆盖目的库。', '操作确认',
      { confirmButtonText: '开始', cancelButtonText: '取消', type: 'warning' })
  } catch { return }

  starting.value = true
  running.value = true
  logs.value = []
  elapsed.value = 0
  taskDone.value = false
  hasTgz.value = false
  downloadName.value = ''
  startTimer()
  try {
    const { data } = await api.conduction.start({ source: config.source, destination: config.destination, skip_import: !skipImport.value })
    taskId.value = data.task_id
    starting.value = false
    pollTask(data.task_id)
  } catch (e) {
    starting.value = false
    running.value = false
    stopTimer()
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
  }
}

function pollTask(id) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const { data } = await api.conduction.taskStatus(id)
      logs.value = data.logs || []
      hasTgz.value = !!data.has_tgz
      taskDone.value = data.status === 'done'
      if (data.tgz_name) downloadName.value = data.tgz_name
      if (data.status === 'done') {
        clearInterval(pollTimer); pollTimer = null
        running.value = false
        stopTimer()
        const failed = (data.logs || []).some(l => !l.success)
        failed ? ElMessage.error('传导结束（含失败步骤，请查看日志）') : ElMessage.success('数据传导完成')
      }
    } catch (e) {
      // 任务不存在（服务端重启等）→ 停止轮询、释放按钮
      if (e?.response?.status === 404) {
        clearInterval(pollTimer); pollTimer = null
        running.value = false
        stopTimer()
        taskId.value = null
      }
    }
  }, 2500)
}

async function downloadTgz() {
  if (!taskId.value) return
  try {
    const res = await api.conduction.download(taskId.value)
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = downloadName.value || 'backup.tgz'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ── timer ──
function startTimer() {
  timerStart = Date.now()
  elapsed.value = 0
  timerRunning.value = true
  ensureTick()
}
function stopTimer() {
  timerRunning.value = false
}
function ensureTick() {
  if (tickInterval) return
  tickInterval = setInterval(() => {
    if (timerRunning.value) elapsed.value = Math.floor((Date.now() - timerStart) / 1000)
  }, 1000)
}
function formatSec(sec) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  const mm = String(m).padStart(2, '0'), ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

const STATE_KEY = 'billsum_conduction_state'
// bump when the persisted shape / endpoint defaults change, to drop stale cache
const DEFAULTS_VER = 4

async function loadServerConfig() {
  try {
    const { data } = await api.conduction.getConfig()
    groups.value = data.groups || []
    if (!selectedName.value || !groups.value.some(g => g.name === selectedName.value)) {
      selectedName.value = data.selected || (groups.value[0]?.name || '')
    }
    loadGroupIntoForm(selectedName.value)
    addNew.value = (selectedName.value === DEFAULT_GROUP_NAME)
  } catch { /* keep defaults */ }
}

function saveState() {
  const s = {
    defaultsVer: DEFAULTS_VER,
    groups: groups.value,
    selectedName: selectedName.value,
    addNew: addNew.value,
    source: config.source,
    destination: config.destination,
    sourceTables: sourceTables.value,
    logs: logs.value,
    elapsed: elapsed.value,
    timerRunning: timerRunning.value,
    timerStart,
    taskId: taskId.value,
    hasTgz: hasTgz.value,
    downloadName: downloadName.value,
    taskDone: taskDone.value,
  }
  try { localStorage.setItem(STATE_KEY, JSON.stringify(s)) } catch { /* ignore */ }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STATE_KEY)
    if (!raw) return false
    const s = JSON.parse(raw)
    if (s.defaultsVer !== DEFAULTS_VER) return false
    groups.value = s.groups || []
    selectedName.value = s.selectedName || ''
    addNew.value = !!s.addNew
    if (s.source) patchEndpoint(config.source, s.source)
    if (s.destination) patchEndpoint(config.destination, s.destination)
    sourceTables.value = s.sourceTables || []
    logs.value = s.logs || []
    elapsed.value = s.elapsed || 0
    timerRunning.value = !!s.timerRunning
    timerStart = s.timerStart || 0
    taskId.value = s.taskId || null
    hasTgz.value = !!s.hasTgz
    downloadName.value = s.downloadName || ''
    taskDone.value = !!s.taskDone
    return true
  } catch { return false }
}

// persist working state across tab/route switches and page reloads
watch(
  [() => config, groups, selectedName, addNew, logs, elapsed, timerRunning, taskId, sourceTables, hasTgz, downloadName, taskDone],
  saveState,
  { deep: true }
)

onMounted(async () => {
  ensureTick()
  const restored = loadState()
  if (!restored) await loadServerConfig()
  // resume polling if a transfer was (or may still be) running
  if (taskId.value) {
    running.value = true
    pollTask(taskId.value)
  }
})

onUnmounted(() => {
  if (tickInterval) { clearInterval(tickInterval); tickInterval = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
})
</script>

<style scoped>
.conduction-panel { padding: 4px; height: 100%; overflow-x: hidden; overflow-y: auto; }
.group-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.group-label { color: #606266; font-size: 14px; }
.ep-title { font-weight: bold; }
.timer-bar { text-align: center; margin-top: 12px; font-family: Consolas, monospace; font-size: 14px; color: #606266; }
.timer-running { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #67c23a; margin-left: 6px; vertical-align: middle; animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
.log-area { margin-top: 12px; background: #1e1e1e; padding: 12px; border-radius: 4px; min-height: 320px; }
.log-line { font-family: Consolas, monospace; font-size: 13px; line-height: 1.8; }
.log-ts { color: #909399; margin-right: 8px; }
.log-step { color: #56b6c2; margin-right: 6px; }
.log-success { color: #67c23a; }
.log-error { color: #f56c6c; }
</style>
