import type { ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import Overview from './pages/Overview'
import Inflows from './pages/Inflows'
import FundList from './pages/FundList'
import FundPerformance from './pages/FundPerformance'
import Benchmarks from './pages/Benchmarks'
import Holdings from './pages/Holdings'
import Transactions from './pages/Transactions'
import IngestLog from './pages/IngestLog'
import FinancialYearContributions from './pages/FinancialYearContributions'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Overview />} />
            <Route path="inflows" element={<Inflows />} />
            <Route path="funds" element={<FundList />} />
            <Route path="funds/:id" element={<FundPerformance />} />
            <Route path="benchmarks" element={<Benchmarks />} />
            <Route path="holdings" element={<Holdings />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="ingest-log" element={<IngestLog />} />
            <Route path="tax-year-contributions" element={<FinancialYearContributions />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
