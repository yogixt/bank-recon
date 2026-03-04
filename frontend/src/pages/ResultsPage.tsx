import { useParams } from 'react-router-dom';
import ResultsView from '../components/reconciliation/ResultsView';

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  if (!id) return <p>No session ID</p>;

  return <ResultsView sessionId={id} />;
}
