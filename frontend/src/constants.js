export const FIELD_META = {
  player_id: { label: '玩家 ID', short: 'Player' },
  country: { label: '国家', short: 'Country' },
  device_os: { label: '设备 OS', short: 'OS' },
  level_reached: { label: '等级', short: 'Level' },
  iap_amount: { label: '内购金额', short: 'IAP' },
  session_duration: { label: '在线时长', short: 'Session' },
  last_login: { label: '最近登录', short: 'Login' },
}

export const COLUMN_ORDER = Object.keys(FIELD_META)

export function isBlank(value) {
  return (
    value === null ||
    value === undefined ||
    (typeof value === 'string' && value.trim() === '')
  )
}

export function formatFieldValue(field, value) {
  if (isBlank(value)) return '—'

  if (field === 'iap_amount') {
    const number = Number(value)
    if (Number.isFinite(number)) {
      return number < 0 ? `-$${Math.abs(number).toFixed(2)}` : `$${number.toFixed(2)}`
    }
    return String(value)
  }

  if (field === 'session_duration') {
    const number = Number(value)
    return Number.isFinite(number) ? `${Math.round(number)} min` : String(value)
  }

  if (field === 'level_reached') {
    const number = Number(value)
    return Number.isFinite(number) ? `Lv.${Math.round(number)}` : String(value)
  }

  return String(value)
}

export function formatNumber(value) {
  if (!Number.isFinite(Number(value))) return String(value ?? '—')
  return Number(value).toLocaleString('en-US')
}
