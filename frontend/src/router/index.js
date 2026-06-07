import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/transfer' },
  { path: '/transfer', name: 'transfer', component: () => import('../views/TransferView.vue'), meta: { title: '数据传输' } },
  { path: '/query', name: 'query', component: () => import('../views/QueryView.vue'), meta: { title: '日志查询' } },
  { path: '/stats', name: 'stats', component: () => import('../views/StatsView.vue'), meta: { title: '数据统计' } },
  { path: '/finance', name: 'finance', component: () => import('../views/FinanceView.vue'), meta: { title: '财务报表' } },
  { path: '/config', name: 'config', component: () => import('../views/ConfigView.vue'), meta: { title: '参数配置' } },
  { path: '/system', name: 'system', component: () => import('../views/SystemView.vue'), meta: { title: '系统功能' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
