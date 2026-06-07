<template>
  <el-container class="app-container">
    <el-aside width="200px" class="app-aside">
      <div class="app-logo">BillSum</div>
      <el-menu
        :default-active="currentRoute"
        router
        class="app-menu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/transfer">
          <el-icon><Upload /></el-icon>
          <span>数据传输</span>
        </el-menu-item>
        <el-menu-item index="/query">
          <el-icon><Search /></el-icon>
          <span>日志查询</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据统计</span>
        </el-menu-item>
        <el-menu-item index="/finance">
          <el-icon><DataAnalysis /></el-icon>
          <span>财务报表</span>
        </el-menu-item>
        <el-menu-item index="/config">
          <el-icon><Setting /></el-icon>
          <span>参数配置</span>
        </el-menu-item>
        <el-menu-item index="/system">
          <el-icon><Monitor /></el-icon>
          <span>系统功能</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="app-main">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Upload, Search, DataAnalysis, Setting, Monitor } from '@element-plus/icons-vue'

const route = useRoute()
const currentRoute = computed(() => route.path)
</script>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}
.app-container {
  height: 100vh;
}
.app-aside {
  background: #304156;
  overflow-y: auto;
}
.app-logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
  letter-spacing: 2px;
}
.app-menu {
  border-right: none;
}
.app-menu .el-menu-item:hover {
  background-color: #263445 !important;
}
.app-menu .el-menu-item.is-active {
  background-color: #263445 !important;
}
.app-main {
  background: #f0f2f5;
  overflow: hidden;
  padding: 20px 20px 0 20px;
  width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.app-main > div {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.app-main > div > .el-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.app-main > div > .el-card > .el-card__body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
</style>
