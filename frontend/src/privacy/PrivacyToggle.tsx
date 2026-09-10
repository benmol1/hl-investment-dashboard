import { usePrivacy } from './context'

export default function PrivacyToggle() {
  const { obscured, toggle } = usePrivacy()
  return (
    <button
      onClick={toggle}
      aria-pressed={obscured}
      title={obscured ? 'Cash amounts are hidden — click to show' : 'Hide all cash amounts'}
      className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium border transition-colors ${
        obscured
          ? 'bg-indigo-600 border-indigo-500 text-white'
          : 'border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500'
      }`}
    >
      {obscured ? (
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M10 4c-4.5 0-7.7 3.1-9 6 1.3 2.9 4.5 6 9 6s7.7-3.1 9-6c-1.3-2.9-4.5-6-9-6zm0 10a4 4 0 110-8 4 4 0 010 8zm0-2a2 2 0 100-4 2 2 0 000 4z" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M3.3 2.3a1 1 0 00-1.4 1.4l2.3 2.4C2.8 7.3 1.6 8.9 1 10c1.3 2.9 4.5 6 9 6 1.6 0 3.1-.4 4.4-1.1l2.3 2.3a1 1 0 001.4-1.4L3.3 2.3zM10 14a4 4 0 01-3.7-5.6l1.6 1.6a2 2 0 002.5 2.5l1.6 1.6c-.6.3-1.3.4-2 .4zm0-8c4.5 0 7.7 3.1 9 6-.5 1.1-1.4 2.3-2.5 3.3l-1.5-1.4A4 4 0 0010 6c-.4 0-.7 0-1 .1L7.6 4.7C8.4 4.2 9.2 6 10 6z" />
        </svg>
      )}
      <span>{obscured ? 'Amounts hidden' : 'Hide amounts'}</span>
    </button>
  )
}
