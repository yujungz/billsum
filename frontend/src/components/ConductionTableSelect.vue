<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="表名选择" width="520px" append-to-body
  >
    <div class="ts-toolbar">
      <el-checkbox :model-value="allSelected" @change="onToggleAll">全部</el-checkbox>
      <el-button size="small" :loading="loading" @click="$emit('refresh')">刷新</el-button>
      <span class="ts-hint">
        {{ allSelected ? '整库备份模式（全部）' : `已选 ${selected.length}/${tableRows.length}` }}
      </span>
    </div>
    <el-table
      ref="tableRef"
      :data="tableRows"
      row-key="name"
      height="360"
      @selection-change="onSelectionChange"
      empty-text="暂无表名，请先「测试数据库连接」或「刷新」"
    >
      <el-table-column type="selection" reserve-selection width="42" />
      <el-table-column prop="name" label="表名" />
    </el-table>
    <template #footer>
      <span class="ts-hint" style="margin-right:auto">
        勾选「全部」或选中所有表时，按整库备份方式导出。
      </span>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="confirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  tables: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'update:selected', 'refresh'])

const tableRef = ref(null)
const innerSelected = ref([])

const tableRows = computed(() => props.tables.map(n => ({ name: n })))
const allSelected = computed(
  () => tableRows.value.length > 0 && innerSelected.value.length === tableRows.value.length
)

// (re)apply saved selection whenever the dialog opens or the table list changes
watch(() => props.modelValue, (open) => {
  if (open) applySelection()
})
watch(() => props.tables, () => {
  if (props.modelValue) nextTick(applySelection)
})

function applySelection() {
  nextTick(() => {
    const t = tableRef.value
    if (!t) return
    t.clearSelection()
    const want = new Set(props.selected)
    tableRows.value.forEach(row => {
      if (want.has(row.name)) t.toggleRowSelection(row, true)
    })
    innerSelected.value = [...props.selected]
  })
}

function onSelectionChange(rows) {
  innerSelected.value = rows.map(r => r.name)
}

function onToggleAll(val) {
  const t = tableRef.value
  if (!t) return
  if (val) {
    tableRows.value.forEach(row => t.toggleRowSelection(row, true))
  } else {
    t.clearSelection()
  }
}

function confirm() {
  emit('update:selected', [...innerSelected.value])
  emit('update:modelValue', false)
}
</script>

<style scoped>
.ts-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.ts-hint { color: #909399; font-size: 12px; }
</style>
