<template>
  <div class="system-view">
    <el-card>
      <template #header><span class="card-title">系统功能 - Binlog 管理</span></template>

      <el-space>
        <el-button type="primary" :loading="loading" @click="loadBinlog">刷新</el-button>
        <el-button type="danger" @click="purgeConfirm">清除 Binlog</el-button>
      </el-space>

      <el-table :data="binlogs" border stripe style="margin-top: 16px; width: 100%">
        <el-table-column prop="Log_name" label="日志文件" />
        <el-table-column prop="File_size" label="大小(bytes)" :formatter="formatSize" />
        <el-table-column prop="Encrypted" label="加密" width="80" />
      </el-table>

      <el-descriptions v-if="totalSize" :column="1" border style="margin-top: 16px; max-width: 400px">
        <el-descriptions-item label="总文件数">{{ binlogs.length }}</el-descriptions-item>
        <el-descriptions-item label="总大小">{{ formatSize(null, null, totalSize) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const binlogs = ref([])
const loading = ref(false)

const totalSize = computed(() => binlogs.value.reduce((sum, b) => sum + (b.File_size || 0), 0))

onMounted(() => loadBinlog())

async function loadBinlog() {
  loading.value = true
  try {
    const { data } = await api.system.binlog()
    binlogs.value = data.binlogs || []
  } finally {
    loading.value = false
  }
}

function formatSize(row, col, val) {
  if (!val) return '0'
  if (val > 1073741824) return (val / 1073741824).toFixed(2) + ' GB'
  if (val > 1048576) return (val / 1048576).toFixed(2) + ' MB'
  if (val > 1024) return (val / 1024).toFixed(2) + ' KB'
  return val + ' B'
}

async function purgeConfirm() {
  await ElMessageBox.confirm(
    '确认清除所有 binlog？此操作不可恢复。',
    '警告',
    { confirmButtonText: '确认清除', cancelButtonText: '取消', type: 'warning' }
  )
  await api.system.purge({})
  ElMessage.success('Binlog 已清除')
  await loadBinlog()
}
</script>

<style scoped>
.system-view { width: 100%; }
.card-title { font-size: 16px; font-weight: bold; }
</style>
