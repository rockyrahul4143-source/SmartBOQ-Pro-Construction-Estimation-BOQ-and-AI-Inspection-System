import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  }).format(n)
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  })
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ')
}

export function severityColor(severity: string): string {
  const map: Record<string, string> = {
    none: 'text-green-600 bg-green-50',
    low: 'text-yellow-600 bg-yellow-50',
    moderate: 'text-orange-600 bg-orange-50',
    high: 'text-red-600 bg-red-50',
    critical: 'text-red-800 bg-red-100 font-bold',
  }
  return map[severity] ?? 'text-gray-600 bg-gray-50'
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    draft: 'text-gray-600 bg-gray-100',
    active: 'text-green-700 bg-green-100',
    on_hold: 'text-yellow-700 bg-yellow-100',
    completed: 'text-blue-700 bg-blue-100',
    archived: 'text-gray-400 bg-gray-50',
  }
  return map[status] ?? 'text-gray-600 bg-gray-100'
}
