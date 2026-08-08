import React from 'react';
import styles from './RegimeWidget.module.css';

interface Props {
  data: any;
}

export default function RegimeWidget({ data }: Props) {
  const regimeState = data?.current_regime || 'BULL_VOLATILE';
  
  // Dummy styling logic based on regime
  let color = 'var(--accent-blue)';
  if (regimeState.includes('BULL')) color = 'var(--accent-green)';
  if (regimeState.includes('BEAR')) color = 'var(--accent-red)';
  
  return (
    <div className={styles.container}>
      <div className={styles.label}>Market Regime</div>
      <div className={styles.indicatorWrapper}>
        <div 
          className={styles.glowIndicator} 
          style={{ backgroundColor: color, boxShadow: `0 0 15px ${color}` }}
        />
        <div className={styles.regimeText} style={{ color }}>
          {regimeState.replace('_', ' ')}
        </div>
      </div>
    </div>
  );
}
