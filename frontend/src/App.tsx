import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import HomePage from './pages/HomePage';
import StoragePage from './pages/StoragePage';
import ResultsPage from './pages/ResultsPage';
import HistoryPage from './pages/HistoryPage';
import ChatPage from './pages/ChatPage';
import IngestionPage from './pages/IngestionPage';
import SchedulesPage from './pages/SchedulesPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/storage" element={<StoragePage />} />
        <Route path="/results/:id" element={<ResultsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/chat/:id" element={<ChatPage />} />
        <Route path="/ingestion" element={<IngestionPage />} />
        <Route path="/schedules" element={<SchedulesPage />} />
      </Routes>
    </Layout>
  );
}
