<template>
  <div class="system-view">
    <el-card>
      <template #header><span class="card-title">数据库管理</span></template>

      <el-tabs v-model="sysTab">
        <!-- 子功能 1: Binlog 管理 -->
        <el-tab-pane label="Binlog管理" name="binlog">
          <el-space>
            <el-button type="primary" :loading="loading" @click="loadBinlog">刷新</el-button>
            <el-button type="danger" @click="purgeConfirm">清除 Binlog</el-button>
          </el-space>

          <el-table ref="binlogTable" :data="binlogs" border stripe style="margin-top: 16px; width: 100%"
            @selection-change="onSelectionChange" @select="onSelect">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="Log_name" label="日志文件" />
            <el-table-column prop="File_size" label="大小(bytes)" :formatter="formatSize" />
            <el-table-column prop="Encrypted" label="加密" width="80" />
          </el-table>

          <el-descriptions v-if="totalSize" :column="1" border style="margin-top: 16px; max-width: 400px">
            <el-descriptions-item label="总文件数">{{ binlogs.length }}</el-descriptions-item>
            <el-descriptions-item label="总大小">{{ formatSize(null, null, totalSize) }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 子功能 2: undo 管理 -->
        <el-tab-pane label="undo管理" name="undo">
          <el-space>
            <el-button type="primary" :loading="undoLoading" @click="loadUndo">刷新</el-button>
            <el-button type="danger" :loading="undoPurging" @click="purgeUndoConfirm">清除</el-button>
            <span v-if="undoPurging" class="undo-hint">关闭→等待收缩→激活 中...</span>
          </el-space>

          <el-table ref="undoTable" :data="undoLogs" border stripe style="margin-top: 16px; width: 100%"
            @selection-change="onUndoSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="NAME" label="名称" />
            <el-table-column prop="STATE" label="状态" width="120" />
            <el-table-column prop="size_mb" label="大小(MB)" :formatter="formatMb" width="140" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const sysTab = ref('binlog')

// ── Binlog ──
const binlogs = ref([])
const selected = ref([])
const binlogTable = ref(null)
const loading = ref(false)

const totalSize = computed(() => binlogs.value.reduce((sum, b) => sum + (b.File_size || 0), 0))

async function loadBinlog() {
  loading.value = true
  try {
    const { data } = await api.system.binlog()
    binlogs.value = data.binlogs || []
    nextTick(() => binlogTable.value && binlogTable.value.toggleAllSelection())
  } finally {
    loading.value = false
  }
}

function onSelectionChange(sel) {
  selected.value = sel
}

// 单行勾选/取消时：
//   勾选某条 → 该条及所有更早(时间更小)的记录一并选中
//   取消某条 → 该条及所有更新(时间更大)的记录一并取消
function onSelect(selection, row) {
  const idx = binlogs.value.indexOf(row)
  if (idx < 0) return
  const checked = selection.includes(row)
  binlogs.value.forEach((r, i) => {
    if (checked && i <= idx && !selection.includes(r)) {
      binlogTable.value && binlogTable.value.toggleRowSelection(r, true)
    } else if (!checked && i >= idx && selection.includes(r)) {
      binlogTable.value && binlogTable.value.toggleRowSelection(r, false)
    }
  })
}

function formatSize(row, col, val) {
  if (!val) return '0'
  if (val > 1073741824) return (val / 1073741824).toFixed(2) + ' GB'
  if (val > 1048576) return (val / 1048576).toFixed(2) + ' MB'
  if (val > 1024) return (val / 1024).toFixed(2) + ' KB'
  return val + ' B'
}

async function purgeConfirm() {
  if (!selected.value.length) {
    ElMessage.warning('请至少选择一个日志文件')
    return
  }
  const sorted = [...selected.value].sort((a, b) => a.Log_name.localeCompare(b.Log_name))
  const last = sorted[sorted.length - 1]
  await ElMessageBox.confirm(
    `将清除所选最后一项「${last.Log_name}」（含）及之前的所有 binlog（包括中间未勾选的文件）。此操作不可恢复。`,
    '警告',
    { confirmButtonText: '确认清除', cancelButtonText: '取消', type: 'warning' }
  )
  await api.system.purge({ before: last.Log_name })
  ElMessage.success('Binlog 已清除')
  await loadBinlog()
}

// ── undo ──
const undoLogs = ref([])
const undoSelected = ref([])
const undoTable = ref(null)
const undoLoading = ref(false)
const undoPurging = ref(false)

async function loadUndo() {
  undoLoading.value = true
  try {
    const { data } = await api.system.undo()
    undoLogs.value = data.undo_logs || []
  } finally {
    undoLoading.value = false
  }
}

function onUndoSelectionChange(sel) {
  undoSelected.value = sel
}

function formatMb(row, col, val) {
  return val != null ? Number(val).toFixed(2) + ' MB' : ''
}

async function purgeUndoConfirm() {
  if (!undoSelected.value.length) {
    ElMessage.warning('请选择要清除的 undo 表空间')
    return
  }
  await ElMessageBox.confirm(
    `将对选中的 ${undoSelected.value.length} 个 undo 表空间依次执行：关闭→等待收缩→激活。是否继续？`,
    '提示',
    { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
  )
  undoPurging.value = true
  try {
    const msgs = []
    for (const u of undoSelected.value) {
      const { data } = await api.system.undoPurge({ name: u.NAME })
      msgs.push(`${u.NAME}: ${data.message}`)
    }
    ElMessage.success(msgs.join('；'))
    await loadUndo()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '清除失败')
  } finally {
    undoPurging.value = false
  }
}

onMounted(() => {
  loadBinlog()
  loadUndo()
})
</script>

<style scoped>
.system-view { width: 100%; }
.card-title { font-size: 16px; font-weight: bold; }
.undo-hint { color: #e6a23c; font-size: 13px; }
</style>
