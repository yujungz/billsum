<template>
  <div>
    <el-card>
      <template #header><span class="card-title">日志查询</span></template>
      <div class="query-layout">
        <el-form inline>
          <el-form-item label="站点">
            <el-select v-model="site" @change="loadTables" placeholder="选择站点" style="width: 160px">
              <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-radio-group v-model="tableType" @change="loadTables">
              <el-radio value="raw">原始记录</el-radio>
              <el-radio value="output">统计表</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="表">
            <el-select v-model="selectedTable" style="width: 380px">
              <el-option v-for="t in tables" :key="t.name" :label="t.name" :value="t.name" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="info" plain :icon="Operation" :disabled="!selectedTable" @click="openFieldDialog">字段选择</el-button>
            <el-button type="primary" :loading="loading" @click="doQuery">查询</el-button>
            <el-button type="danger" @click="deleteConfirm">删除表</el-button>
            <el-dropdown split-button type="success" @click="exportConfirm('xlsx')" @command="exportConfirm">
              导出
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="xlsx">Excel (.xlsx)</el-dropdown-item>
                  <el-dropdown-item command="csv">CSV (.csv)</el-dropdown-item>
                  <el-dropdown-item command="sql">SQL (.sql)</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <span v-if="exportTimerText" class="export-timer">{{ exportTimerText }}</span>
            <el-button v-if="canImport" type="warning" :loading="importLoading" @click="triggerImport">导入</el-button>
            <el-button v-if="canParse" type="warning" :loading="parseLoading" @click="doParse">拆解</el-button>
          </el-form-item>
        </el-form>

        <el-form v-if="activeFilters.length" inline class="filter-form">
          <template v-for="f in activeFilters" :key="f.field">
            <el-form-item :label="f.label">
              <template v-if="f.type === 'datetime_range'">
                <el-date-picker v-model="filterValues[f.field + '_start']" type="datetime"
                  format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss"
                  :default-time="defaultStartTime"
                  placeholder="起始时间" style="width: 200px" />
                <span style="margin: 0 4px">~</span>
                <el-date-picker v-model="filterValues[f.field + '_end']" type="datetime"
                  format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss"
                  :default-time="defaultEndTime"
                  placeholder="截止时间" style="width: 200px" />
              </template>
              <template v-else-if="f.type === 'date_range'">
                <el-date-picker v-model="filterValues[f.field + '_start']" type="date"
                  format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="起始日期" style="width: 150px" />
                <span style="margin: 0 4px">~</span>
                <el-date-picker v-model="filterValues[f.field + '_end']" type="date"
                  format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="截止日期" style="width: 150px" />
              </template>
              <template v-else>
                <el-input v-model="filterValues[f.field]" :placeholder="f.label" clearable style="width: 150px" />
              </template>
            </el-form-item>
          </template>
          <el-form-item v-if="isLogsTable" label="时间排序">
            <el-select v-model="timeOrder" style="width: 100px">
              <el-option label="倒序" value="desc" />
              <el-option label="正序" value="asc" />
            </el-select>
          </el-form-item>
        </el-form>

        <div ref="tableWrapper" class="table-wrapper">
          <el-table :data="tableData" border stripe :height="tableHeight" v-loading="loading" style="width: 100%">
            <el-table-column v-for="col in displayColumns" :key="col.name" :prop="col.name" :label="col.label"
              :min-width="getColumnWidth(col)" show-overflow-tooltip />
          </el-table>
        </div>

        <PaginationBar
          :total="total"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          @change="loadData"
        />
      </div>
    </el-card>

    <el-dialog v-model="fieldDialog" :title="`字段选择 — ${selectedTable}`" width="680px" append-to-body>
      <div class="field-dialog-toolbar">
        <el-checkbox v-model="fieldAll">全选</el-checkbox>
        <span class="field-count">{{ fieldSelectedCount }}/{{ fieldRows.length }} 字段</span>
      </div>
      <el-table :data="fieldRows" border max-height="440" size="small">
        <el-table-column label="显示" width="64" align="center">
          <template #default="{ row }">
            <el-checkbox v-model="row.selected" />
          </template>
        </el-table-column>
        <el-table-column label="字段名" prop="name" width="220" />
        <el-table-column label="中文标题">
          <template #default="{ row }">
            <el-input v-model="row.label" placeholder="留空则用字段名" />
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="fieldDialog = false">取消</el-button>
        <el-button type="primary" @click="saveFields">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Operation } from '@element-plus/icons-vue'
import api from '../api'
import PaginationBar from '../components/PaginationBar.vue'

const sites = ['ai', 'csp', 'pinova', 'wzg', 'qn', 'digitalcloud', 'wshk']
const site = ref('pinova')
const tableType = ref('output')
const tables = ref([])
const selectedTable = ref('')
const tableData = ref([])
const columns = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(parseInt(localStorage.getItem('billsum_page_size')) || 20)
const loading = ref(false)
const importLoading = ref(false)
const parseLoading = ref(false)
const exportTimerText = ref('')

const canImport = computed(() => ['ex_channels', 'ex_tokens', 'ex_users'].includes(selectedTable.value))
const canParse = computed(() => ['channels', 'tokens', 'users'].includes(selectedTable.value))

// ── Timer helpers ──
function startTimer() {
  const t0 = Date.now()
  exportTimerText.value = '导出中 0.0s'
  const timer = setInterval(() => {
    exportTimerText.value = `导出中 ${((Date.now() - t0) / 1000).toFixed(1)}s`
  }, 100)
  return { t0, timer }
}

function stopTimer(t0, timer) {
  clearInterval(timer)
  exportTimerText.value = `耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`
}

// ── Field selection (column visibility + Chinese labels) ──
const FIELDS_KEY_PREFIX = 'billsum_query_fields_'
const fieldConfig = reactive({})      // { colName: { selected, label } }
const fieldRows = ref([])             // editable copy for the dialog
const fieldDialog = ref(false)

const displayColumns = computed(() =>
  columns.value
    .filter(c => fieldConfig[c.name]?.selected !== false)
    .map(c => ({ name: c.name, label: fieldConfig[c.name]?.label || c.name }))
)

const fieldAll = computed({
  get: () => fieldRows.value.length > 0 && fieldRows.value.every(r => r.selected),
  set: (v) => { fieldRows.value.forEach(r => r.selected = v) },
})
const fieldSelectedCount = computed(() => fieldRows.value.filter(r => r.selected).length)

function fieldConfigKey(table) {
  // 统计版 logs 系列（logs* 且非 orig）结构相同，共用同一份字段配置
  if (table && table.startsWith('logs') && !table.endsWith('orig')) return 'logs_output'
  return table
}

function loadFieldConfig() {
  const t = selectedTable.value
  let saved = {}
  if (t) {
    try {
      const raw = localStorage.getItem(FIELDS_KEY_PREFIX + fieldConfigKey(t))
      saved = raw ? JSON.parse(raw) : {}
    } catch { saved = {} }
  }
  Object.keys(fieldConfig).forEach(k => delete fieldConfig[k])
  for (const c of columns.value) {
    const s = saved[c.name]
    fieldConfig[c.name] = (s && typeof s === 'object')
      ? { selected: s.selected !== false, label: s.label || c.name }
      : { selected: true, label: c.name }
  }
}

function saveFieldConfig() {
  if (!selectedTable.value) return
  localStorage.setItem(FIELDS_KEY_PREFIX + fieldConfigKey(selectedTable.value), JSON.stringify(fieldConfig))
}

async function openFieldDialog() {
  if (!columns.value.length) await loadColumns()
  fieldRows.value = columns.value.map(c => ({
    name: c.name,
    selected: fieldConfig[c.name]?.selected !== false,
    label: fieldConfig[c.name]?.label || c.name,
  }))
  fieldDialog.value = true
}

function saveFields() {
  for (const r of fieldRows.value) {
    fieldConfig[r.name] = { selected: r.selected, label: (r.label || r.name) }
  }
  saveFieldConfig()
  fieldDialog.value = false
  ElMessage.success('字段配置已保存')
}

// ── Filter config per table ──
const TABLE_FILTERS = {
  channels: [
    { field: 'name', label: '渠道名称', type: 'string' },
    { field: 'group', label: '分组', type: 'string' },
    { field: 'base_url', label: '基础地址', type: 'string' },
    { field: 'models', label: '模型名称', type: 'string' },
  ],
  tokens: [
    { field: 'name', label: 'token名称', type: 'string' },
    { field: 'group', label: '分组', type: 'string' },
    { field: 'user_id', label: '用户ID', type: 'number' },
  ],
  users: [
    { field: 'username', label: '用户名称', type: 'string' },
    { field: 'group', label: '分组', type: 'string' },
    { field: 'remark', label: '备注', type: 'string' },
  ],
  ex_channels: [
    { field: 'name', label: '渠道名称', type: 'string' },
    { field: 'buyer', label: '采购员', type: 'string' },
    { field: 'supplier', label: '供应商', type: 'string' },
  ],
  ex_tokens: [
    { field: 'name', label: 'token名称', type: 'string' },
    { field: 'user_id', label: '用户ID', type: 'number' },
  ],
  ex_users: [
    { field: 'username', label: '用户名称', type: 'string' },
    { field: 'seller', label: '销售员', type: 'string' },
    { field: 'remark', label: '备注', type: 'string' },
  ],
}

const LOGS_RAW_FILTERS = [
  { field: 'created_at', label: '时间', type: 'datetime_range' },
  { field: 'username', label: '用户名称', type: 'string' },
  { field: 'token_name', label: 'token名称', type: 'string' },
  { field: 'model_name', label: '模型名称', type: 'string' },
  { field: 'group', label: '分组', type: 'string' },
  { field: 'channel_id', label: '渠道标识', type: 'number' },
]

const LOGS_OUTPUT_FILTERS = [
  { field: 'created_at', label: '时间', type: 'datetime_range' },
  { field: 'username', label: '用户名称', type: 'string' },
  { field: 'token_name', label: 'token名称', type: 'string' },
  { field: 'model_name', label: '模型名称', type: 'string' },
  { field: 'group', label: '分组', type: 'string' },
  { field: 'channel_id', label: '渠道标识', type: 'number' },
  { field: 'channel_name', label: '渠道名称', type: 'string' },
  { field: 'us_salesperson', label: '销售员', type: 'string' },
  { field: 'cn_buyer1', label: '采购员', type: 'string' },
  { field: 'cn_supplier1', label: '供应商', type: 'string' },
]

const isLogsTable = computed(() => selectedTable.value?.startsWith('logs'))
const timeOrder = ref('desc')

const defaultStartTime = new Date(2000, 0, 1, 0, 0, 0)
const defaultEndTime = new Date(2000, 0, 1, 23, 59, 59)

const activeFilters = computed(() => {
  const t = selectedTable.value
  if (!t) return []
  if (TABLE_FILTERS[t]) return TABLE_FILTERS[t]
  if (t.startsWith('logs')) {
    return t.endsWith('orig') ? LOGS_RAW_FILTERS : LOGS_OUTPUT_FILTERS
  }
  return []
})

const filterValues = reactive({})

// columns cache: { "site:table": columns[] }
const _columnsCache = reactive({})

// reset filter values when table changes
watch(selectedTable, () => {
  Object.keys(filterValues).forEach(k => delete filterValues[k])
})

// rebuild field selection when columns (re)load
watch(columns, () => loadFieldConfig())

function buildFilters() {
  const result = {}
  for (const f of activeFilters.value) {
    if (f.type === 'datetime_range' || f.type === 'date_range') {
      const start = filterValues[f.field + '_start']
      const end = filterValues[f.field + '_end']
      if (start) {
        // for date_range type, append default time
        result[f.field + '_start'] = f.type === 'date_range' ? start + ' 00:00:00' : start
      }
      if (end) {
        result[f.field + '_end'] = f.type === 'date_range' ? end + ' 23:59:59' : end
      }
    } else {
      const v = filterValues[f.field]
      if (v !== undefined && v !== null && v !== '') {
        result[f.field] = f.type === 'number' ? Number(v) : v
      }
    }
  }
  return Object.keys(result).length ? result : null
}

const tableWrapper = ref(null)
const tableHeight = ref(400)
let resizeObserver = null

onMounted(() => {
  loadTables()
  nextTick(() => {
    if (tableWrapper.value) {
      resizeObserver = new ResizeObserver(entries => {
        tableHeight.value = Math.floor(entries[0].contentRect.height)
      })
      resizeObserver.observe(tableWrapper.value)
    }
  })
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
})

async function loadTables() {
  selectedTable.value = ''
  tableData.value = []
  columns.value = []
  total.value = 0
  const { data } = await api.query.tables(site.value, tableType.value)
  tables.value = data.tables || []
}

function doQuery() {
  page.value = 1
  loadData()
}

async function loadColumns() {
  if (!selectedTable.value) return
  const cacheKey = `${site.value}:${selectedTable.value}`
  if (_columnsCache[cacheKey]) {
    columns.value = _columnsCache[cacheKey]
    return
  }
  const { data } = await api.query.columns(site.value, selectedTable.value)
  const cols = data.columns || []
  _columnsCache[cacheKey] = cols
  columns.value = cols
}

async function loadData() {
  if (!selectedTable.value) return
  loading.value = true
  try {
    const to = isLogsTable.value ? timeOrder.value : null
    // columns: use cache if available, otherwise fetch in parallel
    const cacheKey = `${site.value}:${selectedTable.value}`
    const colsPromise = _columnsCache[cacheKey]
      ? Promise.resolve({ data: { columns: _columnsCache[cacheKey] } })
      : api.query.columns(site.value, selectedTable.value).then(res => {
          _columnsCache[cacheKey] = res.data.columns || []
          return res
        })
    const [dataRes, colRes] = await Promise.all([
      api.query.data(site.value, selectedTable.value, page.value, pageSize.value, buildFilters(), to),
      colsPromise,
    ])
    tableData.value = dataRes.data.data || []
    total.value = dataRes.data.total || 0
    columns.value = colRes.data.columns || []
  } finally {
    loading.value = false
  }
}

async function deleteConfirm() {
  if (!selectedTable.value) {
    ElMessage.warning('请先选择表')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认删除表 "${selectedTable.value}"？此操作不可恢复。`,
      '警告',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  await api.query.deleteTable(site.value, selectedTable.value)
  ElMessage.success('表已删除')
  selectedTable.value = ''
  tableData.value = []
  total.value = 0
  await loadTables()
}

async function exportConfirm(format) {
  if (!selectedTable.value) {
    ElMessage.warning('请先选择表')
    return
  }

  const fileName = `${site.value}_${selectedTable.value}.${format === 'xlsx' ? 'xlsx' : format === 'csv' ? 'csv' : 'sql'}`
  const filters = buildFilters()
  const filterStr = filters ? JSON.stringify(filters) : ''
  const fieldsArr = displayColumns.value.map(c => ({ name: c.name, label: c.label }))
  const fieldsStr = fieldsArr.length ? `&fields=${encodeURIComponent(JSON.stringify(fieldsArr))}` : ''
  const url = `/api/query/export?site=${site.value}&table=${selectedTable.value}&format=${format}${filterStr ? `&filters=${encodeURIComponent(filterStr)}` : ''}${fieldsStr}`

  const { t0, timer } = startTimer()
  try {
    if (window.showSaveFilePicker) {
      const handle = await window.showSaveFilePicker({
        suggestedName: fileName,
        types: format === 'xlsx'
          ? [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }]
          : format === 'csv'
            ? [{ description: 'CSV文件', accept: { 'text/csv': ['.csv'] } }]
            : [{ description: 'SQL文件', accept: { 'text/plain': ['.sql'] } }],
      })
      const resp = await fetch(url)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(err.detail || '导出失败')
      }
      const blob = await resp.blob()
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
      ElMessage.success(`已保存到 ${handle.name}`)
    } else {
      window.open(url)
    }
    stopTimer(t0, timer)
  } catch (e) {
    stopTimer(t0, timer)
    if (e instanceof DOMException && e.name === 'AbortError') return
    ElMessage.error('导出失败: ' + e.message)
  }
}

function getColumnWidth(col) {
  const textCols = ['channel_name', 'model_name', 'token_name', 'username', 'remark', 'us_remark']
  if (textCols.includes(col.name)) return 180
  return 130
}

function triggerImport() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.sql,.xlsx,.xls,.csv'
  input.onchange = (e) => {
    const file = e.target.files?.[0]
    if (file) doImport(file)
  }
  input.click()
}

async function doImport(file) {
  try {
    await ElMessageBox.confirm(
      `确认导入文件 "${file.name}" 到表 "${selectedTable.value}"？`,
      '导入确认',
      { confirmButtonText: '确认导入', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }
  importLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await api.query.importTable(site.value, selectedTable.value, formData)
    ElMessage.success('导入成功')
    await loadTables()
    if (selectedTable.value) loadData()
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    importLoading.value = false
  }
}

async function doParse() {
  if (!selectedTable.value) return
  const table = selectedTable.value
  parseLoading.value = true
  try {
    const fileName = `${site.value}_ex_${table}.xlsx`
    if (window.showSaveFilePicker) {
      const handle = await window.showSaveFilePicker({
        suggestedName: fileName,
        types: [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
      })
      const resp = await fetch(`/api/query/parse?site=${site.value}&table=${table}`, { method: 'POST' })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(err.detail || '请求失败')
      }
      const blob = await resp.blob()
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
      ElMessage.success(`拆解完成，已保存到 ${handle.name}`)
    } else {
      const resp = await fetch(`/api/query/parse?site=${site.value}&table=${table}`, { method: 'POST' })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(err.detail || '请求失败')
      }
      const blob = await resp.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      a.click()
      window.URL.revokeObjectURL(url)
      ElMessage.success(`拆解完成，已下载 ${fileName}`)
    }
    await loadTables()
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    ElMessage.error('拆解失败: ' + (e.message || '未知错误'))
  } finally {
    parseLoading.value = false
  }
}
</script>

<style scoped>
.card-title { font-size: 16px; font-weight: bold; }
.query-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.filter-form {
  flex-shrink: 0;
}
.table-wrapper {
  flex: 1;
  min-height: 0;
}
.export-timer {
  display: inline-block;
  margin-left: 12px;
  color: #67c23a;
  font-size: 13px;
  font-weight: 500;
}
.field-dialog-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; }
.field-count { color: #909399; font-size: 12px; }
:deep(.el-card__body) {
  overflow: hidden !important;
}
</style>
