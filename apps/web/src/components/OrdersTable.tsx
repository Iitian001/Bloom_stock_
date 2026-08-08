'use client';

import React, { useEffect, useState } from 'react';
import styles from './OrdersTable.module.css';

export default function OrdersTable() {
  const [orders, setOrders] = useState<any[]>([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/portfolio/orders')
      .then(res => res.json())
      .then(data => setOrders(data))
      .catch(err => console.error('Failed to fetch orders', err));
  }, []);

  return (
    <div className={styles.tableContainer}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>Recent Orders</h3>
        <span className={styles.countBadge}>{orders.length} Total</span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Time</th>
              <th>Instrument</th>
              <th>Side</th>
              <th className={styles.rightAlign}>Qty</th>
              <th className={styles.rightAlign}>Price</th>
              <th className={styles.rightAlign}>Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id}>
                <td className={styles.time}>{new Date(o.created_at).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' })}</td>
                <td className={styles.instrument}>{o.instrument_id}</td>
                <td className={o.side === 'BUY' ? styles.buy : styles.sell}>{o.side}</td>
                <td className={styles.rightAlign}>{o.quantity}</td>
                <td className={styles.rightAlign}>{o.price?.toFixed(2) || '-'}</td>
                <td className={styles.rightAlign}>
                  <span className={`${styles.badge} ${styles[o.state.toLowerCase()] || styles.defaultBadge}`}>
                    {o.state}
                  </span>
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>No recent orders</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
