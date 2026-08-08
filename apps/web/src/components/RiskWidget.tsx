import React from 'react';
import styles from './RiskWidget.module.css';

interface Props {
  data: any;
}

export default function RiskWidget({ data }: Props) {
  const marginUsage = data?.margin_consumption_pct || 0;
  const drawdown = data?.current_drawdown_pct || 0;
  
  // Example dummy data if real data is missing
  const marginDisp = data ? marginUsage : 45.2;
  const drawdownDisp = data ? drawdown : 2.1;

  const marginColor = marginDisp > 80 ? 'var(--accent-red)' : (marginDisp > 50 ? '#f59e0b' : 'var(--accent-blue)');
  const ddColor = drawdownDisp > 5 ? 'var(--accent-red)' : 'var(--accent-green)';

  return (
    <div className={`${styles.widget} glass-panel animate-slide-in`}>
      <h3 className={styles.title}>Risk Management</h3>
      
      <div className={styles.gauges}>
        {/* Margin Gauge */}
        <div className={styles.gaugeContainer}>
          <div className={styles.gaugeHeader}>
            <span className={styles.gaugeLabel}>Margin Consumption</span>
            <span className={styles.gaugeValue}>{marginDisp.toFixed(1)}%</span>
          </div>
          <div className={styles.barBackground}>
            <div 
              className={styles.barFill} 
              style={{ width: `${Math.min(100, marginDisp)}%`, backgroundColor: marginColor }}
            />
          </div>
        </div>

        {/* Drawdown Gauge */}
        <div className={styles.gaugeContainer}>
          <div className={styles.gaugeHeader}>
            <span className={styles.gaugeLabel}>Current Drawdown</span>
            <span className={styles.gaugeValue} style={{ color: ddColor }}>{drawdownDisp.toFixed(2)}%</span>
          </div>
          <div className={styles.barBackground}>
            <div 
              className={styles.barFill} 
              style={{ width: `${Math.min(100, drawdownDisp * 10)}%`, backgroundColor: ddColor }}
            />
          </div>
        </div>
      </div>

      <div className={styles.statsGrid}>
        <div className={styles.statBox}>
          <div className={styles.statLabel}>Open Pos</div>
          <div className={styles.statVal}>{data?.open_positions_count || 12}</div>
        </div>
        <div className={styles.statBox}>
          <div className={styles.statLabel}>Daily VaR</div>
          <div className={styles.statVal}>${data?.daily_var?.toLocaleString() || '14,200'}</div>
        </div>
      </div>
    </div>
  );
}
