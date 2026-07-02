<template>
  <div class="finance-view">
    <el-card>
      <template #header><span class="card-title">财务报表</span></template>
      <el-tabs v-model="activeTab" class="finance-tabs">
        <!-- Tab 1: 供应商对账 -->
        <el-tab-pane label="供应商对账" name="supplier">
          <div class="tab-layout">
            <el-form :model="supplierForm" label-width="100px" inline>
              <el-form-item label="站点">
                <el-select v-model="supplierForm.site" @change="onSiteChange" placeholder="选择站点" style="width: 140px">
                  <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item label="日志表">
                <el-select v-model="supplierForm.table" @change="onTableChange" placeholder="选择日志表" style="width: 260px">
                  <el-option v-for="t in logTables" :key="t" :label="t" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item label="用户名">
                <el-select v-model="supplierForm.username" filterable placeholder="选择用户名" style="width: 180px">
                  <el-option v-for="u in usernames" :key="u" :label="u" :value="u" />
                </el-select>
              </el-form-item>
              <el-form-item label="起始日期">
                <el-date-picker v-model="supplierForm.dateStart" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
              </el-form-item>
              <el-form-item label="截止日期">
                <el-date-picker v-model="supplierForm.dateEnd" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
              </el-form-item>
              <el-form-item label="供应商名称">
                <el-input v-model="supplierForm.supplierName" placeholder="留空则用 cn_supplier1" clearable style="width: 160px" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="supplierLoading" @click="doSupplierQuery">查询</el-button>
                <el-button :loading="exportLoading" @click="doSupplierExport">导出</el-button>
                <span v-if="exportTimerText" class="export-timer">{{ exportTimerText }}</span>
              </el-form-item>
            </el-form>

            <div ref="supplierTableWrapper" class="table-wrapper">
              <el-table :data="supplierData" border stripe :height="supplierTableHeight" v-loading="supplierLoading"
                style="width: 100%" show-overflow-tooltip>
                <el-table-column v-for="col in supplierColumns" :key="col.key" :prop="col.key" :label="col.label"
                  :width="col.width" :formatter="col.formatter" />
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab 2: 用户统计 -->
        <el-tab-pane label="用户统计" name="userStats">
          <div class="tab-layout">
            <el-form :model="userStatsForm" label-width="100px" inline>
              <el-form-item label="站点">
                <el-select v-model="userStatsForm.site" @change="onUserStatsSiteChange" placeholder="选择站点" style="width: 140px">
                  <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item label="日志表">
                <el-select v-model="userStatsForm.table" @change="onUserStatsTableChange" placeholder="选择日志表" style="width: 260px">
                  <el-option v-for="t in userStatsLogTables" :key="t" :label="t" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item label="用户名">
                <el-select v-model="userStatsForm.username" filterable placeholder="选择用户名" style="width: 180px">
                  <el-option label="全部" value="" />
                  <el-option v-for="u in userStatsUsernames" :key="u" :label="u" :value="u" />
                </el-select>
              </el-form-item>
              <el-form-item label="起始日期">
                <el-date-picker v-model="userStatsForm.dateStart" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
              </el-form-item>
              <el-form-item label="截止日期">
                <el-date-picker v-model="userStatsForm.dateEnd" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
              </el-form-item>
              <el-form-item>
                <el-checkbox v-model="showPlatformQuota" label="平台额度" style="margin-right: 8px" />
                <el-checkbox v-model="showTotalCost" label="消费额度" style="margin-right: 8px" />
                <el-checkbox v-model="showDetail" label="用户明细" style="margin-right: 8px" />
                <span class="granularity-group">
                  <span class="granularity-group-label">统计粒度：</span>
                  <el-checkbox v-model="granularity.model" label="模型名" />
                  <el-checkbox v-model="granularity.token" label="Token名称" />
                </span>
                <el-button type="primary" :loading="userStatsLoading" @click="doUserStatsQuery">查询</el-button>
                <el-checkbox v-if="!userStatsForm.username" v-model="mergeExport" label="合并" style="margin-left: 20px; margin-right: 8px" />
                <el-button type="primary" :icon="Download" :loading="exportLoading" @click="doUserStatsExport">导出</el-button>
                <span v-if="exportTimerText" class="export-timer">{{ exportTimerText }}</span>
              </el-form-item>
            </el-form>

            <el-tabs v-model="userStatsSubTab" class="sub-tabs">
              <el-tab-pane label="月汇总" name="monthly">
                <div ref="monthlyTableWrapper" class="table-wrapper sub-table-wrapper">
                  <el-table :data="userStatsMonthly" border stripe :height="subTableHeight" v-loading="userStatsLoading"
                    style="width: 100%" show-overflow-tooltip show-summary :summary-method="userStatsSummary">
                    <el-table-column v-for="col in userStatsMonthlyCols" :key="col.key" :prop="col.key" :label="col.label"
                      :width="col.width" :formatter="col.formatter" />
                  </el-table>
                </div>
              </el-tab-pane>
              <el-tab-pane label="日统计" name="daily">
                <div ref="dailyTableWrapper" class="table-wrapper sub-table-wrapper">
                  <el-table :data="userStatsDaily" border stripe :height="subTableHeight" v-loading="userStatsLoading"
                    style="width: 100%" show-overflow-tooltip show-summary :summary-method="userStatsSummary">
                    <el-table-column v-for="col in userStatsDailyCols" :key="col.key" :prop="col.key" :label="col.label"
                      :width="col.width" :formatter="col.formatter" />
                  </el-table>
                </div>
              </el-tab-pane>
              <el-tab-pane v-if="showDetail" label="用户明细" name="detail">
                <div ref="detailTableWrapper" class="table-wrapper sub-table-wrapper">
                  <el-table :data="userStatsDetail" border stripe :height="subTableHeight - 42" v-loading="userStatsLoading"
                    style="width: 100%" show-overflow-tooltip show-summary :summary-method="detailSummary">
                    <el-table-column v-for="col in userStatsDetailCols" :key="col.key" :prop="col.key" :label="col.label"
                      :width="col.width" :formatter="col.formatter" />
                  </el-table>
                  <PaginationBar
                    :total="userStatsDetailTotal"
                    v-model:current-page="userStatsDetailPage"
                    v-model:page-size="userStatsDetailPageSize"
                    @change="loadUserStatsDetail"
                  />
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </el-tab-pane>

        <!-- Tab 3: 站点月报 -->
        <el-tab-pane label="站点月报" name="siteMonthly">
          <div class="tab-layout">
            <el-form :model="srForm" label-width="100px" inline>
              <el-form-item label="站点">
                <el-select v-model="srForm.site" @change="onSrSiteChange" placeholder="选择站点" style="width: 140px">
                  <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item label="日志表">
                <el-select v-model="srForm.table" @change="onSrTableChange" placeholder="选择日志表" style="width: 260px">
                  <el-option v-for="t in srLogTables" :key="t" :label="t" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item label="起始日期">
                <el-date-picker v-model="srForm.dateStart" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
              </el-form-item>
              <el-form-item label="截止日期">
                <el-date-picker v-model="srForm.dateEnd" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="srLoading" @click="doSrPreview">查询</el-button>
                <el-button type="success" :loading="srGenerating" @click="doSrGenerate">导出</el-button>
                <span v-if="exportTimerText" class="export-timer">{{ exportTimerText }}</span>
              </el-form-item>
            </el-form>

            <div v-if="srPreview.purchase.length || srPreview.sales.length" class="sr-preview">
              <div v-if="srPreview.purchase.length" class="sr-section">
                <h4>采购提成汇总</h4>
                <el-table :data="srPreview.purchase" border stripe :max-height="300" style="width: 100%" show-overflow-tooltip>
                  <el-table-column prop="采购员" label="采购员" width="100" />
                  <el-table-column prop="供应商数" label="供应商数" width="100" />
                  <el-table-column prop="记录数" label="记录数" width="100" :formatter="fmtInt" />
                  <el-table-column prop="消费额度" label="消费额度" width="120" :formatter="fmt4" />
                  <el-table-column prop="收入" label="收入" width="120" :formatter="fmt4" />
                  <el-table-column prop="成本" label="成本" width="120" :formatter="fmt4" />
                  <el-table-column prop="毛利" label="毛利" width="120" :formatter="fmt4" />
                  <el-table-column prop="采购提成" label="采购提成" width="120" :formatter="fmt4" />
                </el-table>
              </div>

              <div v-if="srPreview.sales.length" class="sr-section">
                <h4>销售提成汇总</h4>
                <el-table :data="srPreview.sales" border stripe :max-height="300" style="width: 100%" show-overflow-tooltip>
                  <el-table-column prop="销售员" label="销售员" width="100" />
                  <el-table-column prop="用户数" label="用户数" width="100" />
                  <el-table-column prop="记录数" label="记录数" width="100" :formatter="fmtInt" />
                  <el-table-column prop="消费额度" label="消费额度" width="120" :formatter="fmt4" />
                  <el-table-column prop="收入" label="收入" width="120" :formatter="fmt4" />
                  <el-table-column prop="成本" label="成本" width="120" :formatter="fmt4" />
                  <el-table-column prop="毛利" label="毛利" width="120" :formatter="fmt4" />
                  <el-table-column prop="提成" label="提成" width="120" :formatter="fmt4" />
                </el-table>
              </div>
            </div>

            <div v-if="srGenerated.total_files > 0" class="sr-result">
              <el-alert type="success" :closable="false" show-icon>
                <template #title>
                  已生成 {{ srGenerated.total_files }} 个报表文件到：{{ srGenerated.report_dir }}
                </template>
              </el-alert>
              <el-table :data="srGenerated.files" border stripe :max-height="300" style="width: 100%; margin-top: 10px">
                <el-table-column type="index" label="#" width="60" />
                <el-table-column prop="" label="文件路径">
                  <template #default="{ row }">{{ row }}</template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import api from '../api'
import PaginationBar from '../components/PaginationBar.vue'

const sites = ['ai', 'csp', 'pinova', 'wzg', 'qn', 'digitalcloud', 'wshk']
const activeTab = ref('supplier')

// ── Shared formatters ──

function fmtInt(row, col, val) {
  return val != null ? Number(val).toLocaleString() : ''
}

function fmt6(row, col, val) {
  return val != null ? Number(val).toFixed(6) : ''
}

function fmt4(row, col, val) {
  return val != null ? Number(val).toFixed(4) : ''
}

// ── Export timer ──

const exportTimerText = ref('')
let _timerInterval = null

function startTimer() {
  const t0 = Date.now()
  exportTimerText.value = '导出中 0.0s'
  clearInterval(_timerInterval)
  _timerInterval = setInterval(() => {
    exportTimerText.value = `导出中 ${((Date.now() - t0) / 1000).toFixed(1)}s`
  }, 100)
  return t0
}

function stopTimer(t0) {
  clearInterval(_timerInterval)
  exportTimerText.value = `耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`
}

// ── Supplier reconciliation ──

const logTables = ref([])
const usernames = ref([])
const supplierData = ref([])
const supplierLoading = ref(false)
const exportLoading = ref(false)

const supplierForm = reactive({
  site: 'pinova',
  table: '',
  username: '',
  dateStart: '',
  dateEnd: '',
  supplierName: '神州数码',
})

const supplierColumns = [
  { key: '日期', label: '日期（每天一行）', width: 120 },
  { key: '模型名称', label: '模型名称', width: 180 },
  { key: '供应商名称', label: '供应商名称', width: 120 },
  { key: '定价单位/tokens数', label: '定价单位/tokens数', width: 150, formatter: fmtInt },
  { key: '定价币种', label: '定价币种', width: 100 },
  { key: '结算含税价input', label: '结算含税价input', width: 140, formatter: fmt6 },
  { key: '结算含税价output', label: '结算含税价output', width: 150, formatter: fmt6 },
  { key: '输入tokens', label: '输入tokens', width: 110, formatter: fmtInt },
  { key: '输出tokens', label: '输出tokens', width: 110, formatter: fmtInt },
  { key: '调用次数', label: '调用次数', width: 90, formatter: fmtInt },
  { key: 'input费用', label: 'input费用', width: 110, formatter: fmt6 },
  { key: 'output费用', label: 'output费用', width: 110, formatter: fmt6 },
  { key: '创建缓存5M', label: '创建缓存5M', width: 110, formatter: fmtInt },
  { key: '创建缓存1H', label: '创建缓存1H', width: 110, formatter: fmtInt },
  { key: '缓存读取', label: '缓存读取', width: 110, formatter: fmtInt },
  { key: '创建缓存5M单价', label: '创建缓存5M单价', width: 120, formatter: fmt6 },
  { key: '创建缓存1H单价', label: '创建缓存1H单价', width: 120, formatter: fmt6 },
  { key: '缓存读取单价', label: '缓存读取单价', width: 120, formatter: fmt6 },
  { key: '创建缓存5M费用', label: '创建缓存5M费用', width: 130, formatter: fmt6 },
  { key: '创建缓存1H费用', label: '创建缓存1H费用', width: 130, formatter: fmt6 },
  { key: '缓存读取费用', label: '缓存读取费用', width: 120, formatter: fmt6 },
  { key: 'cache的token', label: 'cache的token', width: 120, formatter: fmtInt },
  { key: 'cache的金额', label: 'cache的金额', width: 110, formatter: fmt6 },
  { key: '总费用（USD）', label: '总费用（USD）', width: 130, formatter: fmt6 },
]

const supplierTableWrapper = ref(null)
const supplierTableHeight = ref(400)
let supplierResizeObserver = null

onMounted(async () => {
  await loadLogTables()
  await onUserStatsSiteChange()
  await onSrSiteChange()
  // restore saved user-stats granularity
  try {
    const raw = localStorage.getItem(GRANULARITY_KEY)
    if (raw) Object.assign(granularity, JSON.parse(raw))
  } catch { /* ignore */ }
  nextTick(() => {
    if (supplierTableWrapper.value) {
      supplierResizeObserver = new ResizeObserver(entries => {
        supplierTableHeight.value = Math.floor(entries[0].contentRect.height)
      })
      supplierResizeObserver.observe(supplierTableWrapper.value)
    }
    observeSubWrapper()
  })
})

onUnmounted(() => {
  if (supplierResizeObserver) supplierResizeObserver.disconnect()
  if (subResizeObserver) subResizeObserver.disconnect()
})

async function loadLogTables() {
  supplierForm.table = ''
  supplierForm.username = ''
  supplierForm.dateStart = ''
  supplierForm.dateEnd = ''
  usernames.value = []
  const { data } = await api.finance.logTables(supplierForm.site)
  logTables.value = data.tables || []
  if (logTables.value.length > 0) {
    supplierForm.table = logTables.value[logTables.value.length - 1]
    await onTableChange(supplierForm.table)
  }
}

async function onSiteChange() {
  await loadLogTables()
}

async function onTableChange(table) {
  if (!table) return
  supplierForm.dateStart = ''
  supplierForm.dateEnd = ''
  try {
    const { data: dd } = await api.finance.tableDates(table)
    supplierForm.dateStart = dd.start || ''
    supplierForm.dateEnd = dd.end || ''
    const usrRes = await api.finance.usernames(supplierForm.site, table).catch(() => ({ data: { usernames: [] } }))
    const newUsernames = usrRes.data.usernames || []
    if (!newUsernames.includes(supplierForm.username)) supplierForm.username = ''
    usernames.value = newUsernames
  } catch (e) {
    console.error('onTableChange failed', e)
  }
}

async function doSupplierQuery() {
  if (!supplierForm.table) { ElMessage.warning('请选择日志表'); return }
  if (!supplierForm.username) { ElMessage.warning('请选择用户名'); return }

  supplierLoading.value = true
  try {
    const params = {
      site: supplierForm.site,
      table: supplierForm.table,
      username: supplierForm.username,
      supplier_name: supplierForm.supplierName,
    }
    if (supplierForm.dateStart) params.date_start = supplierForm.dateStart
    if (supplierForm.dateEnd) params.date_end = supplierForm.dateEnd
    const { data } = await api.finance.supplier(params)
    supplierData.value = data.rows || []
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '查询失败'
    ElMessage.error(msg)
  } finally {
    supplierLoading.value = false
  }
}

async function doSupplierExport() {
  if (!supplierData.value.length) {
    ElMessage.warning('没有数据可导出，请先查询')
    return
  }
  exportLoading.value = true
  const t0 = startTimer()
  try {
    const params = new URLSearchParams({
      site: supplierForm.site,
      table: supplierForm.table,
      username: supplierForm.username,
      date_start: supplierForm.dateStart || '',
      date_end: supplierForm.dateEnd || '',
      supplier_name: supplierForm.supplierName,
    })
    const ds = (supplierForm.dateStart || '').replace(/-/g, '')
    const de = (supplierForm.dateEnd || '').replace(/-/g, '')
    const fileName = `supplier${ds}_${de}_${supplierForm.username}.xlsx`
    await exportViaFetch(`/api/finance/supplier/export?${params}`, fileName)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    ElMessage.error('导出失败: ' + e.message)
  } finally {
    stopTimer(t0)
    exportLoading.value = false
  }
}

// ── User statistics ──

const userStatsLogTables = ref([])
const userStatsUsernames = ref([])
const userStatsMonthly = ref([])
const userStatsDaily = ref([])
const userStatsDetail = ref([])
const userStatsDetailTotal = ref(0)
const userStatsDetailPage = ref(1)
const userStatsDetailPageSize = ref(parseInt(localStorage.getItem('billsum_page_size')) || 20)
const userStatsLoading = ref(false)
const userStatsSubTab = ref('monthly')

const showTotalCost = ref(false)
const showPlatformQuota = ref(true)
const batchExport = ref(false)
const showDetail = ref(false)
const mergeExport = ref(false)
const GRANULARITY_KEY = 'billsum_user_stats_granularity'
const granularity = reactive({ model: false, token: false })

function saveGranularity() {
  try { localStorage.setItem(GRANULARITY_KEY, JSON.stringify({ ...granularity })) } catch {}
}

const granularityStr = computed(() => {
  const parts = []
  if (granularity.model) parts.push('model')
  if (granularity.token) parts.push('token')
  return parts.join(',')
})

const userStatsForm = reactive({
  site: 'pinova',
  table: '',
  username: '',          // '' = 全部
  dateStart: '',
  dateEnd: '',
})

const monthlyTableWrapper = ref(null)
const dailyTableWrapper = ref(null)
const detailTableWrapper = ref(null)
const subTableHeight = ref(350)
const userStatsDetailTotals = ref({})
let subResizeObserver = null

function observeSubWrapper() {
  if (subResizeObserver) subResizeObserver.disconnect()
  const tabMap = { monthly: monthlyTableWrapper, daily: dailyTableWrapper, detail: detailTableWrapper }
  const wrapper = (tabMap[userStatsSubTab.value] || monthlyTableWrapper).value
  if (wrapper) {
    subResizeObserver = new ResizeObserver(entries => {
      subTableHeight.value = Math.floor(entries[0].contentRect.height)
    })
    subResizeObserver.observe(wrapper)
  }
}

watch(userStatsSubTab, () => nextTick(observeSubWrapper))

// 取消「明细」时清空明细数据，并切回月汇总
watch(showDetail, (v) => {
  if (!v) {
    userStatsDetail.value = []
    userStatsDetailTotal.value = 0
    userStatsDetailTotals.value = {}
    if (userStatsSubTab.value === 'detail') userStatsSubTab.value = 'monthly'
  }
})

const _platformKeys = ['平台额度']

// Keys that should NOT be summed in summary rows (IDs, names, dates, unit prices)
const _NO_SUM_KEYS_STATS = new Set([
  '结算周期', '用户名', '模型名', '用户ID', 'Token名称', '日期',
  '序号', '时间',
  '输入单价', '输出单价', '读取缓存单价', '创建缓存5M单价', '创建缓存1H单价',
])

function userStatsSummary({ columns, data }) {
  return columns.map((col, i) => {
    if (i === 0) return '合计'
    const key = col.property
    if (!key || _NO_SUM_KEYS_STATS.has(key)) return ''
    const vals = data.map(r => Number(r[key])).filter(v => !isNaN(v))
    if (!vals.length) return ''
    const sum = vals.reduce((a, b) => a + b, 0)
    // Match the column's formatter
    const colDef = userStatsMonthlyCols.value.find(c => c.key === key)
      || userStatsDailyCols.value.find(c => c.key === key)
      || userStatsDetailCols.value.find(c => c.key === key)
    if (colDef?.formatter === fmt6) return sum.toFixed(6)
    if (colDef?.formatter === fmt4) return sum.toFixed(4)
    if (colDef?.formatter === fmtInt) return sum.toLocaleString()
    return sum.toLocaleString()
  })
}

// Detail summary uses backend-computed totals across ALL records (not just current page)
function detailSummary({ columns }) {
  const totals = userStatsDetailTotals.value
  return columns.map((col, i) => {
    if (i === 0) return '合计'
    const key = col.property
    if (!key || _NO_SUM_KEYS_STATS.has(key)) return ''
    const val = totals[key]
    if (val == null || isNaN(val)) return ''
    const colDef = userStatsDetailCols.value.find(c => c.key === key)
    if (colDef?.formatter === fmt6) return Number(val).toFixed(6)
    if (colDef?.formatter === fmt4) return Number(val).toFixed(4)
    if (colDef?.formatter === fmtInt) return Number(val).toLocaleString()
    return Number(val).toLocaleString()
  })
}

const userStatsMonthlyCols = computed(() => {
  const cols = [
    { key: '结算周期', label: '结算周期', width: 100 },
    { key: '用户名', label: '用户名', width: 120 },
  ]
  if (granularity.model) cols.push({ key: '模型名', label: '模型名', width: 180 })
  cols.push(
    { key: '输入token(M)', label: '输入token(M)', width: 120, formatter: fmt4 },
    { key: '输出token(M)', label: '输出token(M)', width: 120, formatter: fmt4 },
  )
  if (showTotalCost.value) cols.push({ key: '消费额度', label: '消费额度', width: 120, formatter: fmt6 })
  if (showPlatformQuota.value) cols.push({ key: '平台额度', label: '平台额度', width: 120, formatter: fmt6 })
  return cols
})

const userStatsDailyCols = computed(() => {
  const cols = [
    { key: '用户ID', label: '用户ID', width: 80 },
    { key: '用户名', label: '用户名', width: 100 },
  ]
  if (granularity.token) cols.push({ key: 'Token名称', label: 'Token名称', width: 120 })
  if (granularity.model) cols.push({ key: '模型名', label: '模型名', width: 160 })
  cols.push(
    { key: '日期', label: '日期', width: 110 },
    { key: '结算周期', label: '结算周期', width: 100 },
    { key: '输入token(M)', label: '输入token(M)', width: 120, formatter: fmt4 },
    { key: '输出token(M)', label: '输出token(M)', width: 120, formatter: fmt4 },
    { key: '创建缓存5M(M)', label: '创建缓存5M(M)', width: 140, formatter: fmt4 },
    { key: '创建缓存1H(M)', label: '创建缓存1H(M)', width: 140, formatter: fmt4 },
    { key: '读取缓存(M)', label: '读取缓存(M)', width: 130, formatter: fmt4 },
  )
  if (showTotalCost.value) cols.push({ key: '消费额度', label: '消费额度', width: 110, formatter: fmt6 })
  if (showPlatformQuota.value) cols.push({ key: '平台额度', label: '平台额度', width: 110, formatter: fmt6 })
  return cols
})

const userStatsDetailCols = computed(() => {
  const cols = [
    { key: '序号', label: '序号', width: 80, formatter: fmtInt },
    { key: '用户ID', label: '用户ID', width: 80 },
    { key: '用户名', label: '用户名', width: 100 },
    { key: 'Token名称', label: 'Token名称', width: 120 },
    { key: '模型名', label: '模型名', width: 160 },
    { key: '时间', label: '时间', width: 160 },
    { key: '输入token', label: '输入token', width: 100, formatter: fmtInt },
    { key: '输入单价', label: '输入单价', width: 90, formatter: fmt6 },
    { key: '输入费用', label: '输入费用', width: 100, formatter: fmt6 },
    { key: '输出token', label: '输出token', width: 100, formatter: fmtInt },
    { key: '输出单价', label: '输出单价', width: 90, formatter: fmt6 },
    { key: '输出费用', label: '输出费用', width: 100, formatter: fmt6 },
    { key: '读取缓存token', label: '读取缓存token', width: 110, formatter: fmtInt },
    { key: '读取缓存单价', label: '读取缓存单价', width: 110, formatter: fmt6 },
    { key: '读取缓存费用', label: '读取缓存费用', width: 110, formatter: fmt6 },
    { key: '创建缓存5M-token', label: '创建缓存5M-token', width: 130, formatter: fmtInt },
    { key: '创建缓存5M单价', label: '创建缓存5M单价', width: 120, formatter: fmt6 },
    { key: '创建缓存5M费用', label: '创建缓存5M费用', width: 120, formatter: fmt6 },
    { key: '创建缓存1H-token', label: '创建缓存1H-token', width: 130, formatter: fmtInt },
    { key: '创建缓存1H单价', label: '创建缓存1H单价', width: 120, formatter: fmt6 },
    { key: '创建缓存1H费用', label: '创建缓存1H费用', width: 120, formatter: fmt6 },
    { key: '创建缓存token', label: '创建缓存token', width: 110, formatter: fmtInt },
    { key: '创建缓存费用', label: '创建缓存费用', width: 110, formatter: fmt6 },
    { key: '缓存总token', label: '缓存总token', width: 110, formatter: fmtInt },
    { key: '缓存总费用', label: '缓存总费用', width: 100, formatter: fmt6 },
    { key: '总消耗token', label: '总消耗token', width: 110, formatter: fmtInt },
  ]
  if (showTotalCost.value) cols.push({ key: '消费额度', label: '消费额度', width: 100, formatter: fmt6 })
  if (showPlatformQuota.value) cols.push({ key: '平台额度', label: '平台额度', width: 100, formatter: fmt6 })
  return cols
})

async function onUserStatsSiteChange() {
  userStatsForm.table = ''
  userStatsForm.username = ''
  userStatsForm.dateStart = ''
  userStatsForm.dateEnd = ''
  userStatsUsernames.value = []
  const { data } = await api.finance.logTables(userStatsForm.site)
  userStatsLogTables.value = data.tables || []
  if (userStatsLogTables.value.length > 0) {
    userStatsForm.table = userStatsLogTables.value[userStatsLogTables.value.length - 1]
    await onUserStatsTableChange(userStatsForm.table)
  }
}

async function onUserStatsTableChange(table) {
  if (!table) return
  userStatsForm.dateStart = ''
  userStatsForm.dateEnd = ''
  try {
    const { data: dd } = await api.finance.tableDates(table)
    userStatsForm.dateStart = dd.start || ''
    userStatsForm.dateEnd = dd.end || ''
    const usrRes = await api.finance.usernames(userStatsForm.site, table).catch(() => ({ data: { usernames: [] } }))
    const newUsernames = usrRes.data.usernames || []
    if (!newUsernames.includes(userStatsForm.username)) userStatsForm.username = ''
    userStatsUsernames.value = newUsernames
  } catch (e) {
    console.error('onUserStatsTableChange failed', e)
  }
}

async function doUserStatsQuery() {
  if (!userStatsForm.table) { ElMessage.warning('请选择日志表'); return }

  userStatsLoading.value = true
  try {
    const params = {
      site: userStatsForm.site,
      table: userStatsForm.table,
      username: userStatsForm.username,
      granularity: granularityStr.value,
    }
    if (userStatsForm.dateStart) params.date_start = userStatsForm.dateStart
    if (userStatsForm.dateEnd) params.date_end = userStatsForm.dateEnd
    const { data } = await api.finance.userStats(params)
    saveGranularity()
    userStatsMonthly.value = data.monthly || []
    userStatsDaily.value = data.daily || []
    userStatsDetailTotal.value = 0
    userStatsDetail.value = []
    userStatsDetailTotals.value = {}
    // 仅当勾选「明细」时才加载用户明细
    if (showDetail.value) {
      if (userStatsDetailPage.value !== 1) {
        userStatsDetailPage.value = 1
      }
      await loadUserStatsDetail()
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '查询失败'
    ElMessage.error(msg)
  } finally {
    userStatsLoading.value = false
  }
}

async function loadUserStatsDetail() {
  if (!userStatsForm.table) return
  userStatsLoading.value = true
  try {
    const params = {
      site: userStatsForm.site,
      table: userStatsForm.table,
      username: userStatsForm.username,
      page: userStatsDetailPage.value,
      size: userStatsDetailPageSize.value,
    }
    if (userStatsForm.dateStart) params.date_start = userStatsForm.dateStart
    if (userStatsForm.dateEnd) params.date_end = userStatsForm.dateEnd
    const { data } = await api.finance.userStatsDetail(params)
    userStatsDetail.value = data.data || []
    userStatsDetailTotal.value = data.total || 0
    userStatsDetailTotals.value = data.totals || {}
  } catch (e) {
    console.error('loadUserStatsDetail failed', e)
  } finally {
    userStatsLoading.value = false
  }
}

async function doUserStatsExport() {
  const isBatch = !userStatsForm.username && !mergeExport.value   // 全部+合并→单文件；全部+非合并→按用户
  if (!isBatch && !userStatsMonthly.value.length && !userStatsDaily.value.length && !userStatsDetailTotal.value) {
    ElMessage.warning('没有数据可导出，请先查询')
    return
  }
  try {
    if (isBatch) {
      exportLoading.value = true
      const t0 = startTimer()
      try {
        await _doBatchExport()
      } finally {
        stopTimer(t0)
        exportLoading.value = false
      }
    } else {
      // Issue save picker FIRST, nothing else before it
      const ds = (userStatsForm.dateStart || '').replace(/-/g, '')
      const de = (userStatsForm.dateEnd || '').replace(/-/g, '')
      const fileName = `${userStatsForm.site}_${userStatsForm.username}_${ds}_${de}.xlsx`

      let saveHandle = null
      if (window.showSaveFilePicker) {
        try {
          saveHandle = await window.showSaveFilePicker({
            suggestedName: fileName,
            types: [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
          })
        } catch (e) {
          if (e instanceof DOMException && e.name === 'AbortError') return
          throw e
        }
      }

      // Picker confirmed — now start working
      exportLoading.value = true
      const t0 = startTimer()
      try {
        await _doSingleExport(saveHandle, fileName)
      } finally {
        stopTimer(t0)
        exportLoading.value = false
      }
    }
    saveGranularity()
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    ElMessage.error('导出失败: ' + e.message)
  } finally {
    exportLoading.value = false
  }
}

async function _doSingleExport(saveHandle, fileName) {
  // Start async export task
  const { data: td } = await api.finance.exportAsync({
    site: userStatsForm.site,
    table: userStatsForm.table,
    username: userStatsForm.username,
    date_start: userStatsForm.dateStart || '',
    date_end: userStatsForm.dateEnd || '',
    with_platform: showPlatformQuota.value,
    with_detail: showDetail.value,
    with_total_cost: showTotalCost.value,
    granularity: granularityStr.value,
  })
  const taskId = td.task_id

  // Poll until done
  const ok = await _pollExportTask(taskId, userStatsForm.username)
  if (!ok) {
    const { data: st } = await api.finance.exportStatus(taskId).catch(() => ({ data: {} }))
    throw new Error(st.error || '导出任务失败')
  }

  // Download and save
  const { data: blob } = await api.finance.exportDownload(taskId)

  if (saveHandle) {
    const writable = await saveHandle.createWritable()
    await writable.write(blob)
    await writable.close()
    ElMessage.success(`已保存到 ${saveHandle.name}`)
  } else {
    downloadBlob(blob, fileName)
    ElMessage.success('导出完成')
  }
}

async function _doBatchExport() {
  // Pick directory
  let startIn
  const saved = await _loadDirHandle()
  if (saved && (await saved.queryPermission({ mode: 'readwrite' })) === 'granted') {
    startIn = saved
  }
  let dirHandle
  try {
    dirHandle = await window.showDirectoryPicker({ mode: 'readwrite', startIn })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    ElMessage.error('无法打开文件夹选择器: ' + e.message)
    return
  }
  await _saveDirHandle(dirHandle)

  // Timer starts after directory is confirmed
  const t0 = startTimer()
  try {
    // Fetch all usernames
    const { data: ud } = await api.finance.usernames(userStatsForm.site, userStatsForm.table)
    const users = ud.usernames || []
    if (!users.length) { ElMessage.warning('未找到用户'); return }

    // Create subfolder: site + YYYYMM
    const ym = (userStatsForm.dateStart || '').replace(/-/g, '').substring(0, 6)
    const subDirName = `${userStatsForm.site}_user${ym}`
    const subDir = await dirHandle.getDirectoryHandle(subDirName, { create: true })

    const ds = (userStatsForm.dateStart || '').replace(/-/g, '')
    const de = (userStatsForm.dateEnd || '').replace(/-/g, '')
    let failed = 0

    for (let i = 0; i < users.length; i++) {
      const user = users[i]
      exportTimerText.value = `正在导出 ${user} (${i + 1}/${users.length})...`
      try {
        // Start async export task
        const { data: td } = await api.finance.exportAsync({
          site: userStatsForm.site,
          table: userStatsForm.table,
          username: user,
          date_start: userStatsForm.dateStart || '',
          date_end: userStatsForm.dateEnd || '',
          with_platform: showPlatformQuota.value,
          with_detail: showDetail.value,
          with_total_cost: showTotalCost.value,
          granularity: granularityStr.value,
        })
        const taskId = td.task_id

        // Poll until done
        const ok = await _pollExportTask(taskId, user)
        if (!ok) { failed++; continue }

        // Download file
        const { data: blob } = await api.finance.exportDownload(taskId)
        const fileName = `${userStatsForm.site}_${user}_${ds}_${de}.xlsx`
        const fh = await subDir.getFileHandle(fileName, { create: true })
        const writable = await fh.createWritable()
        await writable.write(blob)
        await writable.close()
      } catch {
        failed++
      }
    }

    if (failed === users.length) {
      ElMessage.error('所有文件导出失败')
    } else {
      ElMessage.success(`已导出 ${users.length - failed}/${users.length} 个文件到 ${subDirName}`)
    }
    batchExport.value = false
  } finally {
    stopTimer(t0)
  }
}

function _pollExportTask(taskId, username) {
  return new Promise((resolve) => {
    const poll = setInterval(async () => {
      try {
        const { data } = await api.finance.exportStatus(taskId)
        if (data.status === 'done') {
          clearInterval(poll)
          resolve(true)
        } else if (data.status === 'failed') {
          clearInterval(poll)
          console.error(`导出失败: ${username}`, data.error)
          resolve(false)
        } else if (data.progress) {
          exportTimerText.value = `${username}: ${data.progress}`
        }
      } catch { /* keep polling */ }
    }, 3000)
  })
}

// ── Site monthly report ──

const srLogTables = ref([])
const srLoading = ref(false)
const srGenerating = ref(false)

const srForm = reactive({
  site: 'pinova',
  table: '',
  dateStart: '',
  dateEnd: '',
})

const srPreview = reactive({
  purchase: [],
  sales: [],
})

const srGenerated = reactive({
  report_dir: '',
  files: [],
  total_files: 0,
})

async function onSrSiteChange() {
  srForm.table = ''
  srForm.dateStart = ''
  srForm.dateEnd = ''
  const { data } = await api.finance.logTables(srForm.site)
  srLogTables.value = data.tables || []
  if (srLogTables.value.length > 0) {
    srForm.table = srLogTables.value[srLogTables.value.length - 1]
    await onSrTableChange(srForm.table)
  }
}

async function onSrTableChange(table) {
  if (!table) return
  const { data: dd } = await api.finance.tableDates(table)
  if (dd.start) srForm.dateStart = dd.start
  if (dd.end) srForm.dateEnd = dd.end
}

async function doSrPreview() {
  if (!srForm.table) { ElMessage.warning('请选择日志表'); return }

  srLoading.value = true
  srGenerated.total_files = 0
  srGenerated.files = []
  try {
    const params = { site: srForm.site, table: srForm.table }
    if (srForm.dateStart) params.date_start = srForm.dateStart
    if (srForm.dateEnd) params.date_end = srForm.dateEnd
    const { data } = await api.finance.siteReportPreview(params)
    srPreview.purchase = data.purchase || []
    srPreview.sales = data.sales || []
  } catch (e) {
    const msg = e.response?.data?.detail || e.message
    ElMessage.error(msg)
  } finally {
    srLoading.value = false
  }
}

// ── Directory handle persistence via IndexedDB ──
const _DIR_DB = 'billsum'
const _DIR_STORE = 'handles'
const _SR_DIR_KEY = 'srExportDir'

function _openDirDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(_DIR_DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(_DIR_STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function _saveDirHandle(handle) {
  const db = await _openDirDB()
  const tx = db.transaction(_DIR_STORE, 'readwrite')
  tx.objectStore(_DIR_STORE).put(handle, _SR_DIR_KEY)
  return new Promise((resolve, reject) => { tx.oncomplete = resolve; tx.onerror = () => reject(tx.error) })
}

async function _loadDirHandle() {
  try {
    const db = await _openDirDB()
    const tx = db.transaction(_DIR_STORE, 'readonly')
    const req = tx.objectStore(_DIR_STORE).get(_SR_DIR_KEY)
    return new Promise(resolve => { req.onsuccess = () => resolve(req.result || null); req.onerror = () => resolve(null) })
  } catch { return null }
}

async function doSrGenerate() {
  if (!srForm.table) { ElMessage.warning('请选择日志表'); return }

  // Try to restore previous directory as dialog start hint
  let startIn
  const saved = await _loadDirHandle()
  if (saved && (await saved.queryPermission({ mode: 'readwrite' })) === 'granted') {
    startIn = saved
  }

  let dirHandle
  try {
    dirHandle = await window.showDirectoryPicker({ mode: 'readwrite', startIn })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    ElMessage.error('无法打开文件夹选择器: ' + e.message)
    return
  }

  srGenerating.value = true
  const t0 = startTimer()
  try {
    const body = { site: srForm.site, table: srForm.table }
    if (srForm.dateStart) body.date_start = srForm.dateStart
    if (srForm.dateEnd) body.date_end = srForm.dateEnd
    const { data } = await api.finance.siteReportZip(body)
    await extractZipToDir(data, dirHandle)
    await _saveDirHandle(dirHandle)
    ElMessage.success('报表已导出到所选文件夹')
  } catch (e) {
    const msg = e.response?.data?.detail || e.message
    ElMessage.error(typeof msg === 'string' ? msg : '导出失败')
  } finally {
    stopTimer(t0)
    srGenerating.value = false
  }
}

async function extractZipToDir(arrayBuffer, dirHandle) {
  const entries = await _zipEntries(arrayBuffer)
  if (!entries.length) throw new Error('ZIP 中无文件')
  let failed = 0
  for (const { path, data } of entries) {
    try {
      const parts = path.split('/')
      let parent = dirHandle
      for (let i = 0; i < parts.length - 1; i++) {
        parent = await parent.getDirectoryHandle(parts[i], { create: true })
      }
      const fh = await parent.getFileHandle(parts[parts.length - 1], { create: true })
      const writable = await fh.createWritable()
      await writable.write(data)
      await writable.close()
    } catch (e) {
      failed++
      console.error(`导出失败: ${path}`, e)
    }
  }
  if (failed === entries.length) throw new Error('所有文件导出失败')
}

async function _zipEntries(buf) {
  const view = new DataView(buf)
  const entries = []
  const decoder = new TextDecoder()
  // Collect local file headers
  let off = 0
  while (off < buf.byteLength - 4) {
    const sig = view.getUint32(off, true)
    if (sig !== 0x04034b50) break // not a local file header
    const nameLen = view.getUint16(off + 26, true)
    const extraLen = view.getUint16(off + 28, true)
    const compSize = view.getUint32(off + 18, true)
    const method = view.getUint16(off + 8, true)
    const nameRaw = new Uint8Array(buf, off + 30, nameLen)
    const name = decoder.decode(nameRaw)
    const dataOff = off + 30 + nameLen + extraLen
    let data
    if (method === 0) {
      data = new Uint8Array(buf, dataOff, compSize)
    } else {
      // deflate — use DecompressionStream
      const compressed = new Uint8Array(buf, dataOff, compSize)
      const ds = new DecompressionStream('deflate-raw')
      const writer = ds.writable.getWriter()
      writer.write(compressed)
      writer.close()
      const reader = ds.readable.getReader()
      const chunks = []
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        chunks.push(value)
      }
      const total = chunks.reduce((s, c) => s + c.length, 0)
      data = new Uint8Array(total)
      let p = 0
      for (const c of chunks) { data.set(c, p); p += c.length }
    }
    // skip directories
    if (!name.endsWith('/')) entries.push({ path: name, data })
    off = dataOff + compSize
  }
  return entries
}

// ── Helpers ──

async function exportViaFetch(url, fileName) {
  if (window.showSaveFilePicker) {
    const handle = await window.showSaveFilePicker({
      suggestedName: fileName,
      types: [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
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
    const resp = await fetch(url)
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new Error(err.detail || '导出失败')
    }
    const blob = await resp.blob()
    downloadBlob(blob, fileName)
    ElMessage.success('导出完成')
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.finance-view { width: 100%; }
.card-title { font-size: 16px; font-weight: bold; }
.finance-tabs { height: 100%; display: flex; flex-direction: column; }
.finance-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: auto; }
.finance-tabs :deep(.el-tab-pane) { height: 100%; }
.tab-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.table-wrapper {
  flex: 1;
  min-height: 0;
}
.sub-tabs { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.sub-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow: hidden; }
.sub-tabs :deep(.el-tab-pane) { height: 100%; }
.sub-table-wrapper { height: 100%; }
.sr-section { margin-bottom: 16px; }
.sr-section h4 { margin: 0 0 8px 0; font-size: 14px; }
.sr-preview { overflow: auto; }
.sr-result { margin-top: 12px; }
.export-timer {
  display: inline-block;
  margin-left: 12px;
  color: #67c23a;
  font-size: 13px;
  font-weight: 500;
}
.granularity-group {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 4px 10px; border: 1px solid #dcdfe6; border-radius: 4px;
  margin-right: 8px;
}
.granularity-group-label { color: #606266; font-size: 13px; white-space: nowrap; }
:deep(.el-card__body) { overflow: hidden !important; }
</style>
