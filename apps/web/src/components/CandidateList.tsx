import React from 'react';
import styles from './CandidateList.module.css';

interface Candidate {
  instrument_id: string;
  family: string;
  rank: number;
  take_probability: number;
}

interface Props {
  candidates: Candidate[];
}

export default function CandidateList({ candidates }: Props) {
  if (!candidates || candidates.length === 0) {
    return (
      <div className={`${styles.emptyState} glass-panel`}>
        <div className={styles.spinner}></div>
        <p>Waiting for candidates stream...</p>
      </div>
    );
  }

  return (
    <div className={styles.list}>
      {candidates.map((cand, idx) => (
        <div key={`${cand.instrument_id}-${idx}`} className={`${styles.card} glass-panel animate-slide-in`} style={{ animationDelay: `${idx * 0.05}s` }}>
          <div className={styles.cardHeader}>
            <span className={styles.instrumentId}>{cand.instrument_id}</span>
            <span className={styles.familyBadge}>{cand.family || 'UNKNOWN'}</span>
          </div>
          
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>LGBM Rank</span>
              <span className={styles.metricValue}>{cand.rank != null ? cand.rank.toFixed(2) : '-'}</span>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricLabel}>XGB Prob</span>
              <div className={styles.probBarContainer}>
                <div 
                  className={styles.probBar} 
                  style={{ 
                    width: `${Math.min(100, Math.max(0, (cand.take_probability || 0) * 100))}%`,
                    background: cand.take_probability > 0.7 ? 'var(--accent-green)' : (cand.take_probability > 0.4 ? 'var(--accent-blue)' : 'var(--accent-purple)')
                  }} 
                />
              </div>
              <span className={styles.metricValueSm}>{(cand.take_probability * 100).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
