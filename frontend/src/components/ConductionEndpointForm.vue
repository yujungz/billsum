<template>
  <el-form :model="endpoint" label-width="90px" size="small" class="ep-form">
    <el-form-item label="部署类型">
      <el-radio-group v-model="endpoint.deploy_type">
        <el-radio value="local">本地</el-radio>
        <el-radio value="remote">远程</el-radio>
      </el-radio-group>
    </el-form-item>
    <el-form-item label="运行模式">
      <el-radio-group v-model="endpoint.run_mode">
        <el-radio value="docker">docker</el-radio>
        <el-radio value="host">本机</el-radio>
      </el-radio-group>
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
          <el-button :loading="mountLoading" @click="triggerMount">挂载</el-button>
        </div>
      </el-form-item>
      <el-form-item v-if="endpoint.ssh.auth_method === 'password'" label="密码">
        <el-input v-model="endpoint.ssh.password" type="password" show-password />
      </el-form-item>
      <el-form-item label="用户名">
        <el-input v-model="endpoint.ssh.user" />
      </el-form-item>
      <el-form-item label="主机">
        <el-input v-model="endpoint.ssh.host" placeholder="IP 或域名" />
      </el-form-item>
      <el-form-item label="端口">
        <el-input-number v-model="endpoint.ssh.port" :min="1" :max="65535" controls-position="right" />
      </el-form-item>
      <el-form-item label="远程路径">
        <el-input v-model="endpoint.ssh.remote_path" :placeholder="endpoint.os_type === 'windows' ? 'c:\\data' : '~/data/'" />
      </el-form-item>
      <el-form-item>
        <el-button :loading="sshLoading" @click="testSsh">测试 SSH</el-button>
      </el-form-item>
    </template>

    <!-- Database block -->
    <el-divider content-position="left">数据库</el-divider>
    <el-form-item label="用户名">
      <el-input v-model="endpoint.db.user" />
    </el-form-item>
    <el-form-item label="密码">
      <el-input v-model="endpoint.db.password" type="password" show-password />
    </el-form-item>
    <el-form-item label="数据库名">
      <el-input v-model="endpoint.db.db_name" />
    </el-form-item>
    <el-form-item v-if="endpoint.run_mode === 'docker'" label="容器名称">
      <el-input v-model="endpoint.db.container_name" />
    </el-form-item>
    <template v-else>
      <el-form-item label="服务器">
        <el-input v-model="endpoint.db.host" />
      </el-form-item>
      <el-form-item label="端口">
        <el-input-number v-model="endpoint.db.port" :min="1" :max="65535" controls-position="right" />
      </el-form-item>
    </template>
    <el-form-item>
      <el-button :loading="dbLoading" @click="testDb">测试数据库连接</el-button>
      <el-button v-if="which === 'source'" :loading="dbLoading" @click="testDb">表名选择…</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  endpoint: { type: Object, required: true },
  which: { type: String, default: 'source' },
})
const emit = defineEmits(['tables'])

const sshLoading = ref(false)
const dbLoading = ref(false)
const mountLoading = ref(false)

async function testSsh() {
  sshLoading.value = true
  try {
    const { data } = await api.conduction.testSsh(props.endpoint)
    data.success ? ElMessage.success(data.message) : ElMessage.error(data.message)
  } catch (e) {
    ElMessage.error('SSH 测试失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    sshLoading.value = false
  }
}

async function testDb() {
  dbLoading.value = true
  try {
    const { data } = await api.conduction.testDb(props.endpoint)
    if (data.success) {
      ElMessage.success(data.message)
      if (props.which === 'source') emit('tables', data.tables || [])
    } else {
      ElMessage.error(data.message)
    }
  } catch (e) {
    ElMessage.error('数据库测试失败: ' + (e.response?.data?.detail || e.message))
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
</style>
