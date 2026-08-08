'use client';

import React, { useEffect, useState, useRef } from 'react';
import styles from './Dashboard.module.css';
import CandidateList from './CandidateList';
import RiskWidget from './RiskWidget';
import RegimeWidget from './RegimeWidget';
import PositionsTable from './PositionsTable';
import OrdersTable from './OrdersTable';

export default function Dashboard() {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [regime, setRegime] = useState<any>(null);
  const [risk, setRisk] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Fetch Regime
    fetch('http://localhost:8000/api/v1/regime')
      .then(res => res.json())
      .then(data => setRegime(data))
      .catch(err => console.error('Failed to fetch regime', err));

    // Fetch Risk
    fetch('http://localhost:8000/api/v1/risk/status')
      .then(res => res.json())
      .then(data => setRisk(data))
      .catch(err => console.error('Failed to fetch risk status', err));

    // Connect WebSocket
    const connectWs = () => {
      wsRef.current = new WebSocket('ws://localhost:8000/api/v1/candidates/stream');
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Assuming data is an array of candidates or a single candidate update
          if (Array.isArray(data)) {
            setCandidates(data);
          } else {
            setCandidates(prev => {
              const exists = prev.findIndex(c => c.instrument_id === data.instrument_id);
              if (exists >= 0) {
                const newArr = [...prev];
                newArr[exists] = data;
                return newArr;
              }
              return [data, ...prev].slice(0, 50); // Keep last 50
            });
          }
        } catch (e) {
          console.error("WS Parse Error", e);
        }
      };

      wsRef.current.onclose = () => {
        console.log('WS Disconnected. Reconnecting in 5s...');
        setTimeout(connectWs, 5000);
      };
    };

    connectWs();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return (
    <div className={styles.dashboardContainer}>
      <header className={styles.header}>
        <h1 className={styles.title}>
          <span className={styles.logoMark}>bloom.</span>Stock
          <span className={styles.subtitle}>LIVE SHADOW</span>
        </h1>
        <RegimeWidget data={regime} />
      </header>

      <div className={styles.mainContent}>
        <section className={styles.candidateSection}>
          <div className={styles.sectionHeader}>
            <h2>Candidate Feed</h2>
            <div className={styles.liveIndicator}>
              <span className={styles.pulse}></span>
              Live
            </div>
          </div>
          <CandidateList candidates={candidates} />
        </section>

        <aside className={styles.sidebar}>
          <RiskWidget data={risk} />
        </aside>
      </div>

      <div className={styles.portfolioSection}>
        <div className={styles.sectionHeader}>
          <h2>Paper Trading Portfolio</h2>
        </div>
        <div className={styles.portfolioGrid}>
          <PositionsTable />
          <OrdersTable />
        </div>
      </div>
    </div>
  );
}
