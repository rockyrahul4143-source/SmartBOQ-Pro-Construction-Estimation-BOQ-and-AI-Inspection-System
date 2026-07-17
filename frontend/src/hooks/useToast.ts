import { useState, useEffect } from 'react'

export interface ToastMessage {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'destructive' | 'success'
}

let listeners: Array<(toasts: ToastMessage[]) => void> = []
let toastStore: ToastMessage[] = []

function notify(toast: Omit<ToastMessage, 'id'>) {
  const id = Math.random().toString(36).slice(2)
  toastStore = [...toastStore, { ...toast, id }]
  listeners.forEach(l => l([...toastStore]))
  setTimeout(() => {
    toastStore = toastStore.filter(t => t.id !== id)
    listeners.forEach(l => l([...toastStore]))
  }, 4000)
}

export const toast = {
  success: (title: string, description?: string) =>
    notify({ title, description, variant: 'success' }),
  error: (title: string, description?: string) =>
    notify({ title, description, variant: 'destructive' }),
  info: (title: string, description?: string) =>
    notify({ title, description, variant: 'default' }),
}

export function useToast() {
  const [msgs, setMsgs] = useState<ToastMessage[]>([...toastStore])

  useEffect(() => {
    const handler = (updated: ToastMessage[]) => setMsgs([...updated])
    listeners.push(handler)
    return () => {
      listeners = listeners.filter(l => l !== handler)
    }
  }, [])

  return { toasts: msgs }
}
