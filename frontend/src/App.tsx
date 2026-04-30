import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Contributions from './pages/Contributions'
import FundList from './pages/FundList'
import FundPerformance from './pages/FundPerformance'
import Benchmarks from './pages/Benchmarks'
import Holdings from './pages/Holdings'
import Transactions from './pages/Transactions'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="contributions" element={<Contributions />} />
          <Route path="funds" element={<FundList />} />
          <Route path="funds/:id" element={<FundPerformance />} />
          <Route path="benchmarks" element={<Benchmarks />} />
          <Route path="holdings" element={<Holdings />} />
          <Route path="transactions" element={<Transactions />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
