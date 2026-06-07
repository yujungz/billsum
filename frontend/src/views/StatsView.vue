<template>
  <div class="stats-view">
    <el-card>
      <template #header><span class="card-title">数据统计</span></template>
      <div class="stats-layout">
        <el-form :model="form" label-width="100px" inline>
          <el-form-item label="站点">
            <el-select v-model="form.site" @change="onSiteChange" placeholder="选择站点" style="width: 160px">
              <el-option v-for="s in sites" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="日志表">
            <el-select v-model="form.table_name" @change="onTableChange" style="width: 250px">
              <el-option v-for="t in logTables" :key="t.name" :label="t.name" :value="t.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="起始日期">
            <el-date-picker v-model="form.date_start" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
          </el-form-item>
          <el-form-item label="截止日期">
            <el-date-picker v-model="form.date_end" type="date" value-format="YYYY-MM-DD" style="width: 160px" />
          </el-form-item>
          <el-form-item label="统计粒度">
            <el-checkbox-group v-model="form.group_by">
              <el-checkbox value="month">按月</el-checkbox>
              <el-checkbox value="day">按日</el-checkbox>
              <el-checkbox value="user">用户</el-checkbox>
              <el-checkbox value="channel">渠道</el-checkbox>
              <el-checkbox value="model">模型</el-checkbox>
              <el-checkbox value="token">Token</el-checkbox>
              <el-checkbox value="group">分组</el-checkbox>
              <el-checkbox value="buyer">采购员</el-checkbox>
              <el-checkbox value="supplier">供应商</el-checkbox>
              <el-checkbox value="salesperson">销售员</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>

        <el-form :model="form" label-width="100px" inline>
          <el-form-item label="用户名">
            <el-input v-model="form.filters.username" placeholder="筛选用户" clearable style="width: 150px" />
          </el-form-item>
          <el-form-item label="渠道">
            <el-input v-model="form.filters.channel_name" placeholder="筛选渠道" clearable style="width: 150px" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.filters.model_name" placeholder="筛选模型" clearable style="width: 150px" />
          </el-form-item>
          <el-form-item label="采购员">
            <el-input v-model="form.filters.cn_buyer1" placeholder="筛选采购员" clearable style="width: 150px" />
          </el-form-item>
          <el-form-item label="供应商">
            <el-input v-model="form.filters.cn_supplier1" placeholder="筛选供应商" clearable style="width: 150px" />
          </el-form-item>
          <el-form-item label="销售员">
            <el-input v-model="form.filters.us_salesperson" placeholder="筛选销售员" clearable style="width: 150px" />
          </el-form-item>
          <el-form-item label="0费用">
            <el-radio-group v-model="form.show_zero">
              <el-radio :value="true">显示</el-radio>
              <el-radio :value="false">隐藏</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.desc_order" label="倒序" style="margin-right: 8px" />
            <el-button type="primary" :loading="loading" @click="doQuery">查询</el-button>
            <el-dropdown split-button @click="doExport('xlsx')" @command="doExport">
              导出 Excel
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="xlsx">Excel (.xlsx)</el-dropdown-item>
                  <el-dropdown-item command="csv">CSV (.csv)</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </el-form-item>
        </el-form>

        <div ref="tableWrapper" class="table-wrapper">
          <el-table :data="pagedData" border stripe :height="tableHeight" v-loading="loading" style="width: 100%"
            show-summary :summary-method="getSummary">
            <el-table-column v-for="col in resultColumns" :key="col.key" :prop="col.key" :label="col.label"
              :width="col.width" :formatter="col.formatter" show-overflow-tooltip />
          </el-table>
        </div>

        <PaginationBar
          :total="statsData.length"
          v-model:current-page="page"
          v-model:page-size="pageSize"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import PaginationBar from '../components/PaginationBar.vue'

defineOptions({ name: 'StatsView' })

const sites = ['ai', 'csp', 'pinova', 'wzg', 'qn', 'digitalcloud']
const logTables = ref([])
const statsData = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(parseInt(localStorage.getItem('billsum_page_size')) || 20)

const pagedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return statsData.value.slice(start, start + pageSize.value)
})

const form = reactive({
  site: 'pinova',
  table_name: '',
  date_start: '',
  date_end: '',
  group_by: [],
  show_zero: true,
  desc_order: true,
  filters: {
    username: '',
    channel_name: '',
    model_name: '',
    cn_buyer1: '',
    cn_supplier1: '',
    us_salesperson: '',
  },
})

// 粒度维度 → 对应的列 key
const GROUP_COL_KEYS = {
  month: ['period_month'],
  day: ['period_day'],
  user: ['user_id', 'username'],
  channel: ['channel_id', 'channel_name'],
  model: ['model_name'],
  token: ['token_name'],
  group: ['group_name'],
  buyer: ['cn_buyer1'],
  supplier: ['cn_supplier1'],
  salesperson: ['us_salesperson'],
}

const allColumns = [
  { key: 'period_month', label: '月份', width: 100 },
  { key: 'period_day', label: '日期', width: 110 },
  { key: 'user_id', label: '用户ID', width: 80 },
  { key: 'username', label: '用户名', width: 120 },
  { key: 'channel_id', label: '渠道ID', width: 80 },
  { key: 'channel_name', label: '渠道', width: 120 },
  { key: 'model_name', label: '模型', width: 160 },
  { key: 'token_name', label: 'Token', width: 120 },
  { key: 'group_name', label: '分组', width: 120 },
  { key: 'cn_buyer1', label: '采购员', width: 100 },
  { key: 'cn_supplier1', label: '供应商', width: 100 },
  { key: 'us_salesperson', label: '销售员', width: 100 },
  { key: 'call_count', label: '调用次数', width: 90, formatter: fmtInt },
  { key: 'input_tokens', label: '输入token', width: 110, formatter: fmtInt },
  { key: 'input_unit_price', label: '输入单价', width: 90, formatter: fix6 },
  { key: 'input_cost', label: '输入费用', width: 100, formatter: fix6 },
  { key: 'output_tokens', label: '输出token', width: 110, formatter: fmtInt },
  { key: 'output_unit_price', label: '输出单价', width: 90, formatter: fix6 },
  { key: 'output_cost', label: '输出费用', width: 100, formatter: fix6 },
  { key: 'cache_read_tokens', label: '读取缓存token', width: 120, formatter: fmtInt },
  { key: 'cache_read_unit_price', label: '读取缓存单价', width: 110, formatter: fix6 },
  { key: 'cache_read_cost', label: '读取缓存费用', width: 110, formatter: fix6 },
  { key: 'cache_create_5m_tokens', label: '创建缓存5M-token', width: 140, formatter: fmtInt },
  { key: 'cache_create_5m_unit_price', label: '创建缓存5M单价', width: 130, formatter: fix6 },
  { key: 'cache_create_5m_cost', label: '创建缓存5M费用', width: 130, formatter: fix6 },
  { key: 'cache_create_1h_tokens', label: '创建缓存1H-token', width: 140, formatter: fmtInt },
  { key: 'cache_create_1h_unit_price', label: '创建缓存1H单价', width: 130, formatter: fix6 },
  { key: 'cache_create_1h_cost', label: '创建缓存1H费用', width: 130, formatter: fix6 },
  { key: 'cache_create_tokens', label: '创建缓存token', width: 120, formatter: fmtInt },
  { key: 'cache_create_cost', label: '创建缓存费用', width: 110, formatter: fix6 },
  { key: 'cache_total_tokens', label: '缓存总token', width: 110, formatter: fmtInt },
  { key: 'cache_total_cost', label: '缓存总费用', width: 100, formatter: fix6 },
  { key: 'total_tokens', label: '总消耗token', width: 120, formatter: fmtInt },
  { key: 'total_cost', label: '消费额度', width: 100, formatter: fix6 },
  { key: 'platform_quota', label: '平台额度', width: 100, formatter: fix6 },
]

// 收集所有粒度相关的列 key，其余为数据列（始终显示）
const groupedKeySet = new Set(Object.values(GROUP_COL_KEYS).flat())

const resultColumns = computed(() => {
  const activeKeys = new Set()
  for (const g of form.group_by) {
    for (const k of (GROUP_COL_KEYS[g] || [])) activeKeys.add(k)
  }
  return allColumns.filter(col => !groupedKeySet.has(col.key) || activeKeys.has(col.key))
})

function fix4(row, col, val) {
  return val != null ? Number(val).toFixed(4) : ''
}

function fix6(row, col, val) {
  return val != null ? Number(val).toFixed(6) : ''
}

function fmtInt(row, col, val) {
  return val != null ? Number(val).toLocaleString() : ''
}

// Columns that should NOT be summed in the summary row
const _NO_SUM_KEYS = new Set([
  'user_id', 'channel_id',
  'input_unit_price', 'output_unit_price', 'cache_read_unit_price',
  'cache_create_5m_unit_price', 'cache_create_1h_unit_price',
])

function getSummary({ columns, data }) {
  const cols = resultColumns.value
  const allRows = statsData.value
  return columns.map((_, i) => {
    const key = cols[i]?.key
    if (!key || _NO_SUM_KEYS.has(key)) return ''
    const vals = allRows.map(r => Number(r[key])).filter(v => !isNaN(v))
    if (!vals.length) return ''
    const sum = vals.reduce((a, b) => a + b, 0)
    // Use the same formatter as the column
    const col = cols[i]
    if (col?.formatter === fmtInt) return sum.toLocaleString()
    if (col?.formatter === fix6) return sum.toFixed(6)
    if (col?.formatter === fix4) return sum.toFixed(4)
    return sum.toLocaleString()
  })
}

function parseTableDates(name) {
  // logs20260401_20260528 -> {start: '2026-04-01', end: '2026-05-28'}
  // logs202605 -> {start: '2026-05-01', end: '2026-05-31'}
  const m1 = name.match(/^logs(\d{8})_(\d{8})$/)
  if (m1) {
    return {
      start: `${m1[1].slice(0, 4)}-${m1[1].slice(4, 6)}-${m1[1].slice(6, 8)}`,
      end: `${m1[2].slice(0, 4)}-${m1[2].slice(4, 6)}-${m1[2].slice(6, 8)}`,
    }
  }
  const m2 = name.match(/^logs(\d{6})$/)
  if (m2) {
    const y = parseInt(m2[1].slice(0, 4))
    const m = parseInt(m2[1].slice(4, 6))
    const lastDay = new Date(y, m, 0).getDate()
    return {
      start: `${y}-${String(m).padStart(2, '0')}-01`,
      end: `${y}-${String(m).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
    }
  }
  return { start: '', end: '' }
}

const tableWrapper = ref(null)
const tableHeight = ref(400)
let resizeObserver = null

onMounted(() => {
  if (!logTables.value.length) loadLogTables()
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

async function loadLogTables() {
  const { data } = await api.query.logTables(form.site)
  logTables.value = (data.tables || []).filter(t => !t.name.endsWith('orig'))
  if (logTables.value.length > 0) {
    form.table_name = logTables.value[logTables.value.length - 1].name
    onTableChange(form.table_name)
  }
}

async function onSiteChange() {
  form.table_name = ''
  form.date_start = ''
  form.date_end = ''
  statsData.value = []
  await loadLogTables()
}

function onTableChange(table) {
  if (!table) return
  const dates = parseTableDates(table)
  form.date_start = dates.start
  form.date_end = dates.end
}

async function doQuery() {
  if (!form.table_name) {
    ElMessage.warning('请选择日志表')
    return
  }
  loading.value = true
  page.value = 1
  try {
    const filters = {}
    if (form.filters.username) filters.username = form.filters.username
    if (form.filters.channel_name) filters.channel_name = form.filters.channel_name
    if (form.filters.model_name) filters.model_name = form.filters.model_name
    if (form.filters.cn_buyer1) filters.cn_buyer1 = form.filters.cn_buyer1
    if (form.filters.cn_supplier1) filters.cn_supplier1 = form.filters.cn_supplier1
    if (form.filters.us_salesperson) filters.us_salesperson = form.filters.us_salesperson
    if (form.date_start) filters.date_start = form.date_start
    if (form.date_end) filters.date_end = form.date_end

    const { data } = await api.stats.query({
      site: form.site,
      table_name: form.table_name,
      group_by: form.group_by,
      filters: Object.keys(filters).length ? filters : null,
      show_zero: form.show_zero,
    })
    const rows = data.data || []
    if (form.desc_order) {
      const dateKey = form.group_by.includes('day') ? 'period_day' : 'period_month'
      rows.sort((a, b) => {
        if (a[dateKey] && b[dateKey]) return b[dateKey].localeCompare(a[dateKey])
        return 0
      })
    }
    statsData.value = rows
  } finally {
    loading.value = false
  }
}

async function doExport(format = 'xlsx') {
  if (!statsData.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }

  const filters = {}
  if (form.filters.username) filters.username = form.filters.username
  if (form.filters.channel_name) filters.channel_name = form.filters.channel_name
  if (form.filters.model_name) filters.model_name = form.filters.model_name
  if (form.filters.cn_buyer1) filters.cn_buyer1 = form.filters.cn_buyer1
  if (form.filters.cn_supplier1) filters.cn_supplier1 = form.filters.cn_supplier1
  if (form.filters.us_salesperson) filters.us_salesperson = form.filters.us_salesperson
  if (form.date_start) filters.date_start = form.date_start
  if (form.date_end) filters.date_end = form.date_end
  const body = {
    site: form.site,
    table_name: form.table_name,
    group_by: form.group_by,
    filters: Object.keys(filters).length ? filters : null,
    show_zero: form.show_zero,
  }

  if (format === 'xlsx') {
    // Backend generates real xlsx via openpyxl
    const fileName = `${form.site}_${form.table_name}_stats.xlsx`
    try {
      if (window.showSaveFilePicker) {
        const handle = await window.showSaveFilePicker({
          suggestedName: fileName,
          types: [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
        })
        const resp = await fetch('/api/stats/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
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
        const resp = await fetch('/api/stats/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({ detail: resp.statusText }))
          throw new Error(err.detail || '导出失败')
        }
        const blob = await resp.blob()
        downloadBlob(blob, fileName)
        ElMessage.success('导出完成')
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return
      ElMessage.error('导出失败: ' + e.message)
    }
  } else {
    // CSV: client-side
    const visibleCols = resultColumns.filter(c => statsData.value.some(r => r[c.key] != null))
    const headers = visibleCols.map(c => c.label)
    const rows = statsData.value.map(r =>
      visibleCols.map(c => {
        const v = r[c.key]
        if (v == null) return ''
        if (typeof v !== 'number') return v
        // Use the column's formatter if available, otherwise toLocaleString
        if (c.formatter) return c.formatter(r, c, v)
        return v.toLocaleString()
      })
    )
    const csv = '﻿' + headers.join(',') + '\n' + rows.map(r => r.join(',')).join('\n')
    downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `${form.table_name}_stats.csv`)
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
.stats-view { width: 100%; }
.card-title { font-size: 16px; font-weight: bold; }
.stats-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.table-wrapper {
  flex: 1;
  min-height: 0;
}
:deep(.el-card__body) {
  overflow: hidden !important;
}
</style>
