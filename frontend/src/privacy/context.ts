import { createContext, useContext } from 'react'

export const STORAGE_KEY = 'hl-dashboard:privacy'

/** Placeholder shown in place of a cash figure when privacy mode is on (charts only). */
export const CASH_MASK = '••••'

export interface PrivacyContextValue {
  /** When true, all cash amounts in the UI are visually obscured. */
  obscured: boolean
  setObscured: (value: boolean) => void
  toggle: () => void
}

export const PrivacyContext = createContext<PrivacyContextValue>({
  obscured: false,
  setObscured: () => {},
  toggle: () => {},
})

export function usePrivacy() {
  return useContext(PrivacyContext)
}

export function readStoredPrivacy(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function writeStoredPrivacy(value: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  } catch {
    /* ignore persistence failures (private mode, etc.) */
  }
}
