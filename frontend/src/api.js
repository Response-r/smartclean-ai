import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail
    let message

    if (error.code === 'ERR_NETWORK' || !error.response) {
      message =
        '无法连接后端服务。请先在项目根目录双击 start_backend.bat，确认 http://127.0.0.1:8000 已启动后再试。'
    } else if (typeof detail === 'string') {
      message = detail
    } else if (Array.isArray(detail)) {
      message = detail.map((item) => item.msg || '参数校验失败').join('；')
    } else if (error.code === 'ECONNABORTED') {
      message = '请求超时，数据量可能过大，请稍后重试。'
    } else {
      message = `请求失败（HTTP ${error.response.status}），请稍后重试。`
    }

    return Promise.reject(new Error(message))
  },
)

export const fetchHealth = () => http.get('/health')

export const generateMockData = () => http.post('/generate-mock-data')

export const inspectUpload = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return http.post('/inspect-upload', formData)
}

export const confirmUpload = (pendingId, mapping) =>
  http.post('/confirm-upload', { pending_id: pendingId, mapping })

export const cleanDataset = (datasetId) =>
  http.post('/clean-data', { dataset_id: datasetId })

export const downloadCleanedCsv = (datasetId) =>
  http.get(`/export/${datasetId}`, { responseType: 'blob' })
