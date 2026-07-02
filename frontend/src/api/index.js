import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 7200000,
})

export default {
  // Transfer
  transfer: {
    export: (data) => api.post('/transfer/export', data),
    download: (data) => api.post('/transfer/download', data),
    import: (data) => api.post('/transfer/import', data),
    fill: (data) => api.post('/transfer/fill', data),
    all: (data) => api.post('/transfer/all', data),
    asyncAll: (data) => api.post('/transfer/async-all', data),
    taskStatus: (taskId) => api.get('/transfer/task-status', { params: { task_id: taskId } }),
    uptcustomer: (data) => api.post('/transfer/uptcustomer', data),
  },
  // 数据传导 (DB→DB backup/transfer)
  conduction: {
    getConfig: () => api.get('/conduction/config'),
    saveConfig: (data) => api.put('/conduction/config', data),
    testSsh: (data) => api.post('/conduction/test-ssh', data),
    testDb: (data) => api.post('/conduction/test-db', data),
    refreshTables: (data) => api.post('/conduction/refresh-tables', data),
    start: (data) => api.post('/conduction/start', data),
    taskStatus: (taskId) => api.get('/conduction/task-status', { params: { task_id: taskId } }),
    download: (taskId) => api.get('/conduction/download', { params: { task_id: taskId }, responseType: 'blob' }),
  },
  // Finance
  finance: {
    logTables: (site) => api.get('/finance/log-tables', { params: { site } }),
    usernames: (site, table) => api.get('/finance/usernames', { params: { site, table } }),
    tableDates: (table) => api.get('/finance/table-dates', { params: { table } }),
    supplier: (params) => api.get('/finance/supplier', { params }),
    supplierExport: (params) => api.get('/finance/supplier/export', { params, responseType: 'blob' }),
    userStats: (params) => api.get('/finance/user-stats', { params }),
    userStatsDetail: (params) => api.get('/finance/user-stats/detail', { params }),
    userStatsExport: (params) => api.get('/finance/user-stats/export', { params, responseType: 'blob' }),
    exportAsync: (data) => api.post('/finance/user-stats/export-async', data),
    exportStatus: (taskId) => api.get('/finance/user-stats/export-status', { params: { task_id: taskId } }),
    exportDownload: (taskId) => api.get('/finance/user-stats/export-download', { params: { task_id: taskId }, responseType: 'blob' }),
    siteReportPreview: (params) => api.get('/finance/site-report/preview', { params }),
    siteReportGenerate: (data) => api.post('/finance/site-report/generate', data),
    siteReportZip: (data) => api.post('/finance/site-report/generate-zip', data, { responseType: 'arraybuffer' }),
  },

  // Query
  query: {
    tables: (site, type = 'raw') => api.get('/query/tables', { params: { site, type } }),
    logTables: (site) => api.get('/query/log-tables', { params: { site } }),
    columns: (site, table) => api.get('/query/columns', { params: { site, table } }),
    data: (site, table, page = 1, size = 50, filters = null, timeOrder = null) => {
      const params = { site, table, page, size }
      if (filters) params.filters = JSON.stringify(filters)
      if (timeOrder) params.time_order = timeOrder
      return api.get('/query/data', { params })
    },
    deleteTable: (site, table) => api.delete('/query/table', { params: { site, table } }),
    importTable: (site, table, formData) => api.post('/query/import', formData, { params: { site, table }, headers: { 'Content-Type': 'multipart/form-data' } }),
  },
  // Stats
  stats: {
    query: (data) => api.post('/stats/query', data),
    distinct: (site, table, field) => api.get('/stats/distinct', { params: { site, table, field } }),
    exportDetail: (data) => api.post('/stats/export-detail', data, { responseType: 'blob' }),
    exportDetailAsync: (data) => api.post('/stats/export-detail-async', data),
    exportDetailStatus: (taskId) => api.get('/stats/export-detail-status', { params: { task_id: taskId } }),
    exportDetailDownload: (taskId) => api.get('/stats/export-detail-download', { params: { task_id: taskId }, responseType: 'blob' }),
  },
  // Settings
  settings: {
    get: () => api.get('/settings'),
    save: (data) => api.put('/settings', data),
    testMysql: (data) => api.post('/settings/test-mysql', data),
    testSsh: (data) => api.post('/settings/test-ssh', data),
    testRemoteDb: (data) => api.post('/settings/test-remote-db', data),
    mountKey: (formData) => api.post('/settings/mount-key', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  },
  // System
  system: {
    binlog: () => api.get('/system/binlog'),
    purge: (data) => api.post('/system/binlog/purge', data),
    executeSql: (site, formData) => api.post('/system/execute-sql', formData, { params: { site }, headers: { 'Content-Type': 'multipart/form-data' } }),
  },
}
