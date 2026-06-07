<template>
  <div class="pagination-bar" v-if="total > 0">
    <span class="pg-total">共 {{ total }} 条 / {{ totalPages }} 页</span>
    <el-select v-model="innerSize" size="small" class="pg-size" @change="onSizeChange">
      <el-option v-for="s in [10, 20, 50, 100]" :key="s" :value="s" :label="`${s}条/页`" />
    </el-select>
    <div class="pg-nav">
      <button class="pg-btn" :disabled="innerPage <= 10" @click="go(innerPage - 10)" title="后退10页">&laquo;</button>
      <button class="pg-btn" :disabled="innerPage <= 1" @click="go(innerPage - 1)" title="上一页">&lsaquo;</button>
      <button v-for="p in visiblePages" :key="p"
        :class="['pg-btn', 'pg-num', { active: p === innerPage }]"
        @click="go(p)">{{ p }}</button>
      <button class="pg-btn" :disabled="innerPage >= totalPages" @click="go(innerPage + 1)" title="下一页">&rsaquo;</button>
      <button class="pg-btn" :disabled="innerPage + 10 > totalPages" @click="go(innerPage + 10)" title="前进10页">&raquo;</button>
    </div>
    <span class="pg-jump">
      前往 <input class="pg-input" type="number" v-model.number="jumpTo"
        :min="1" :max="totalPages" @keyup.enter="onJump" /> 页
    </span>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})

const emit = defineEmits(['update:currentPage', 'update:pageSize', 'change'])

const innerPage = ref(props.currentPage)
const innerSize = ref(props.pageSize)
const jumpTo = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / innerSize.value)))

const visiblePages = computed(() => {
  const segStart = Math.floor((innerPage.value - 1) / 10) * 10 + 1
  const pages = []
  for (let i = segStart; i < segStart + 10 && i <= totalPages.value; i++) {
    pages.push(i)
  }
  return pages
})

watch(() => props.currentPage, v => { innerPage.value = v })

function go(page) {
  page = Math.max(1, Math.min(totalPages.value, Math.floor(page)))
  if (page === innerPage.value) return
  innerPage.value = page
  jumpTo.value = null
  emit('update:currentPage', page)
  emit('change')
}

function onSizeChange(val) {
  localStorage.setItem('billsum_page_size', String(val))
  innerSize.value = val
  innerPage.value = 1
  emit('update:pageSize', val)
  emit('update:currentPage', 1)
  emit('change')
}

function onJump() {
  if (jumpTo.value && jumpTo.value >= 1 && jumpTo.value <= totalPages.value) {
    go(jumpTo.value)
  }
}
</script>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  justify-content: center;
  flex-wrap: wrap;
  user-select: none;
}
.pg-total { color: #606266; font-size: 13px; white-space: nowrap; }
.pg-size { width: 110px; }
.pg-nav { display: flex; align-items: center; gap: 4px; }
.pg-btn {
  width: 28px; height: 28px;
  border: 1px solid #dcdfe6; border-radius: 4px;
  background: #fff; cursor: pointer;
  font-size: 16px; line-height: 1; color: #606266;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.pg-btn:hover:not(:disabled) { color: #409eff; border-color: #409eff; }
.pg-btn:disabled { color: #c0c4cc; cursor: not-allowed; background: #f5f7fa; }
.pg-num { font-size: 13px; min-width: 28px; }
.pg-num.active { color: #fff; background: #409eff; border-color: #409eff; font-weight: bold; }
.pg-num.active:hover { color: #fff; background: #409eff; border-color: #409eff; }
.pg-info { font-size: 13px; color: #606266; padding: 0 8px; white-space: nowrap; }
.pg-jump {
  font-size: 13px; color: #606266;
  display: flex; align-items: center; gap: 6px; white-space: nowrap;
}
.pg-input {
  width: 50px; height: 28px;
  border: 1px solid #dcdfe6; border-radius: 4px;
  text-align: center; font-size: 13px; outline: none;
  -moz-appearance: textfield;
}
.pg-input::-webkit-inner-spin-button,
.pg-input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.pg-input:focus { border-color: #409eff; }
</style>
