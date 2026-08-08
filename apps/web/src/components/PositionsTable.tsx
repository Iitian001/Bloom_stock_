'use client';

import React, { useEffect, useState } from 'react';
import styles from './PositionsTable.module.css';

export default function PositionsTable() {
  const [positions, setPositions] = useState<any[]>([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/portfolio/positions')
      .then(res => res.json())
      .then(data => setPositions(data))
      .catch(err => console.error('Failed to fetch positions', err));
  }, []);

  return (
    <div className={styles.tableContainer}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Active Positions</h3>
        <span className={styles.countBadge}>{positions.length} Open</span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Instrument</th>
              <th className={styles.rightAlign}>Qty</th>
              <th className={styles.rightAlign}>Avg Price</th>
              <th className={styles.rightAlign}>Realized PnL</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.id}>
                <td className={styles.instrument}>{p.instrument_id}</td>
                <td className={`${styles.rightAlign} ${p.net_quantity > 0 ? styles.buy : p.net_quantity < 0 ? styles.sell : ''}`}>{p.net_quantity}</td>
                <td className={styles.rightAlign}>{p.average_price.toFixed(2)}</td>
                <td className={`${styles.rightAlign} ${p.realized_pnl >= 0 ? styles.positive : styles.negative}`}>
                  {p.realized_pnl >= 0 ? '+' : ''}{p.realized_pnl.toFixed(2)}
                </td>
              </tr>
            ))}
            {positions.length === 0 && (
              <tr>
                <td colSpan={4} className={styles.empty}>No active positions</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
