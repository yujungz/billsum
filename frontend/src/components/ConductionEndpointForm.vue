<template>
  <el-form :model="endpoint" label-width="90px" size="small" class="ep-form">
    <el-form-item label="部署类型">
      <div class="field-row">
        <el-radio-group v-model="endpoint.deploy_type">
          <el-radio value="local">本地</el-radio>
          <el-radio value="remote">远程</el-radio>
        </el-radio-group>
        <template v-if="endpoint.deploy_type === 'remote'">
          <span class="sub-label">运行模式</span>
          <el-radio-group v-model="endpoint.run_mode">
            <el-radio value="docker">docker</el-radio>
            <el-radio value="host">本机</el-radio>
          </el-radio-group>
        </template>
      </div>
    </el-form-item>
    <el-form-item label="操作系统">
      <el-radio-group v-model="endpoint.os_type">
        <el-radio value="windows">Windows</el-radio>
        <el-radio value="linux">Linux</el-radio>
      </el-radio-group>
    </el-form-item>

    <!-- SSH block: remote only -->
    <template v-if="endpoint.deploy_type === 'remote'">
      <el-divider content-position="left">SSH 连接</el-divider>
      <el-form-item label="登录方式">
        <el-radio-group v-model="endpoint.ssh.auth_method">
          <el-radio value="key">密钥</el-radio>
          <el-radio value="password">密码</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="endpoint.ssh.auth_method === 'key'" label="RSA 密钥">
        <div style="display:flex; gap:6px; width:100%">
          <el-input v-model="endpoint.ssh.key_path" placeholder="后端主机内密钥路径" />
          <el-button type="warning" :icon="Upload" :loading="mountLoading" @click="triggerMount">挂载</el-button>
        </div>
      </el-form-item>
      <el-form-item v-if="endpoint.ssh.auth_method === 'password'" label="密码">
        <el-input v-model="endpoint.ssh.password" type="password" show-password />
      </el-form-item>
      <el-form-item label="用户名">
        <div class="field-row">
          <el-input v-model="endpoint.ssh.user" />
          <span class="sub-label">主机</span>
          <el-input v-model="endpoint.ssh.host" placeholder="IP/域名" />
          <span class="sub-label">端口</span>
          <el-input-number v-model="endpoint.ssh.port" :min="1" :max="65535" controls-position="right" />
        </div>
      </el-form-item>
      <el-form-item label="远程路径">
        <el-input v-model="endpoint.ssh.remote_path" :placeholder="endpoint.os_type === 'windows' ? 'c:\\data' : '~/data/'" />
      </el-form-item>
      <el-form-item>
        <el-button type="success" :icon="Link" :loading="sshLoading" @click="testSsh">测试 SSH</el-button>
        <div v-if="sshResult" :class="['result-line', sshResult.ok ? 'ok' : 'err']">{{ sshResult.text }}</div>
      </el-form-item>
    </template>

    <!-- Database block -->
    <el-divider content-position="left">数据库</el-divider>
    <el-form-item label="用户名">
      <div class="field-row">
        <el-input v-model="endpoint.db.user" />
        <span class="sub-label">密码</span>
        <el-input v-model="endpoint.db.password" type="password" show-password />
      </div>
    </el-form-item>
    <el-form-item label="数据库名">
      <el-input v-model="endpoint.db.db_name" />
    </el-form-item>
    <el-form-item v-if="endpoint.run_mode === 'docker'" label="容器名称">
      <el-input v-model="endpoint.db.container_name" />
    </el-form-item>
    <template v-else>
      <el-form-item label="服务器">
        <div class="field-row">
          <el-input v-model="endpoint.db.host" />
          <span class="sub-label">端口</span>
          <el-input-number v-model="endpoint.db.port" :min="1" :max="65535" controls-position="right" />
        </div>
      </el-form-item>
    </template>
    <el-form-item>
      <el-button type="success" :icon="Connection" :loading="dbLoading" @click="testDb">测试数据库连接</el-button>
      <el-button v-if="which === 'source'" type="primary" :icon="Search" :loading="dbLoading" @click="testDb">获取表名</el-button>
      <div v-if="dbResult" :class="['result-line', dbResult.ok ? 'ok' : 'err']">{{ dbResult.text }}</div>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Search, Link, Upload } from '@element-plus/icons-vue'
import api from '../api'

const props = defineProps({
  endpoint: { type: Object, required: true },
  which: { type: String, default: 'source' },
})
const emit = defineEmits(['tables'])

// 本地部署只能用本机模式：应用跑在容器里，无法用 docker 命令访问容器内的库，
// 只能用「服务器名」走 TCP 访问。选「本地」时强制 run_mode=host。
watch(() => props.endpoint.deploy_type, (dt) => {
  if (dt === 'local') props.endpoint.run_mode = 'host'
}, { immediate: true })

const sshLoading = ref(false)
const dbLoading = ref(false)
const mountLoading = ref(false)
const sshResult = ref(null)
const dbResult = ref(null)

function now() {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

async function testSsh() {
  sshLoading.value = true
  try {
    const { data } = await api.conduction.testSsh(props.endpoint)
    sshResult.value = { ok: data.success, text: `${now()} ${data.message}` }
  } catch (e) {
    sshResult.value = { ok: false, text: `${now()} SSH 测试失败: ${e.response?.data?.detail || e.message}` }
  } finally {
    sshLoading.value = false
  }
}

async function testDb() {
  dbLoading.value = true
  try {
    const { data } = await api.conduction.testDb(props.endpoint)
    dbResult.value = { ok: data.success, text: `${now()} ${data.message}` }
    if (data.success && props.which === 'source') emit('tables', data.tables || [])
  } catch (e) {
    dbResult.value = { ok: false, text: `${now()} 数据库测试失败: ${e.response?.data?.detail || e.message}` }
  } finally {
    dbLoading.value = false
  }
}

function triggerMount() {
  const input = document.createElement('input')
  input.type = 'file'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    mountLoading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.settings.mountKey(formData)
      if (data.success) {
        props.endpoint.ssh.key_path = data.container_path
        ElMessage.success(`密钥已挂载: ${data.container_path}`)
      } else {
        ElMessage.error('挂载失败')
      }
    } catch (e) {
      ElMessage.error('挂载失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      mountLoading.value = false
    }
  }
  input.click()
}
</script>

<style scoped>
.ep-form :deep(.el-form-item) { margin-bottom: 12px; }
.ep-form :deep(.el-divider) { margin: 8px 0 14px; }
.field-row { display: flex; gap: 16px; align-items: center; width: 100%; flex-wrap: wrap; }
.field-row .sub-label { color: #606266; font-size: 12px; white-space: nowrap; }
.field-row :deep(.el-input) { flex: 1; min-width: 70px; }
.field-row :deep(.el-input-number) { width: 120px; flex-shrink: 0; }
.result-line { flex-basis: 100%; margin-top: 6px; font-size: 12px; font-family: Consolas, monospace; word-break: break-all; line-height: 1.5; }
.result-line.ok { color: #67c23a; }
.result-line.err { color: #f56c6c; }
</style>
