import { useCallback, useState, type ReactNode } from 'react'
import { PrivacyContext, readStoredPrivacy, writeStoredPrivacy } from './context'

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [obscured, setObscuredState] = useState<boolean>(readStoredPrivacy)

  const setObscured = useCallback((value: boolean) => {
    setObscuredState(value)
    writeStoredPrivacy(value)
  }, [])

  const toggle = useCallback(() => {
    setObscuredState((v) => {
      writeStoredPrivacy(!v)
      return !v
    })
  }, [])

  return (
    <PrivacyContext.Provider value={{ obscured, setObscured, toggle }}>
      {children}
    </PrivacyContext.Provider>
  )
}
