import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="header">
        <div className="container">
          <h1><Link to="/" style={{ color: 'inherit' }}>Bank Reconciliation</Link></h1>
          <nav>
            <Link to="/">Reconcile</Link>
            <Link to="/storage">Storage</Link>
            <Link to="/history">History</Link>
          </nav>
        </div>
      </header>
      <main className="page">
        <div className="container">{children}</div>
      </main>
    </>
  );
}
