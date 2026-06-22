import { useState, useEffect } from 'react'
import * as api from '../services/api'

/**
 * CyberLens — Model Performance Evaluation Page
 *
 * Tabbed interface showing confusion matrices, metrics, and
 * evaluation results for all CyberLens ML models.
 *
 * Tabs: Fingerprinter / Classifier / Deepfake / Decision Engine
 */

const TABS = [
  { id: 'fingerprinter', label: 'Fingerprinter', icon: '🧬' },
  { id: 'classifier', label: 'Scam Classifier', icon: '🏷️' },
  { id: 'deepfake', label: 'Deepfake Detector', icon: '🎭' },
  { id: 'decision', label: 'Decision Engine', icon: '⚖️' },
]

const cardStyle = {
  background: 'var(--bg-secondary)',
  borderRadius: 'var(--radius)',
  padding: '20px 24px',
  border: '1px solid var(--border)',
}

const metricCardStyle = {
  ...cardStyle,
  textAlign: 'center',
  minWidth: 140,
  flex: 1,
}

const FPR_THRESHOLD = 0.05

function MetricCard({ label, value, suffix = '', warning = false, color }) {
  const textColor = warning ? '#ef4444' : color || 'var(--accent)'
  return (
    <div style={metricCardStyle}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600 }}>
        {label}
      </div>
      <div style={{
        fontSize: 28, fontWeight: 800, color: textColor,
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        {value}{suffix}
      </div>
      {warning && (
        <div style={{ fontSize: 10, color: '#ef4444', marginTop: 4, fontWeight: 600 }}>
          ⚠️ Above safe threshold ({FPR_THRESHOLD * 100}%)
        </div>
      )}
    </div>
  )
}

function MatrixImage({ model, alt }) {
  const [src, setSrc] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    setSrc(`/api/evaluation/matrix/${model}?t=${Date.now()}`)
    setError(false)
  }, [model])

  if (error) {
    return (
      <div style={{
        ...cardStyle, textAlign: 'center', padding: 40,
        color: 'var(--text-muted)',
      }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
        <div>No confusion matrix available yet.</div>
        <div style={{ fontSize: 12, marginTop: 4 }}>
          Run the training script first to generate evaluation outputs.
        </div>
      </div>
    )
  }

  return (
    <div style={{ ...cardStyle, padding: 12, textAlign: 'center' }}>
      <img
        src={src}
        alt={alt}
        onError={() => setError(true)}
        style={{
          maxWidth: '100%',
          borderRadius: 8,
          background: '#fff',
        }}
      />
    </div>
  )
}

function StatusBadge({ status }) {
  const colors = {
    evaluated: { bg: '#22c55e20', text: '#22c55e', label: '✓ Evaluated' },
    not_trained: { bg: '#f59e0b20', text: '#f59e0b', label: '⏳ Not Trained' },
    no_data: { bg: '#ef444420', text: '#ef4444', label: '✗ No Data' },
    import_error: { bg: '#ef444420', text: '#ef4444', label: '✗ Import Error' },
  }
  const c = colors[status] || colors.not_trained
  return (
    <span style={{
      background: c.bg, color: c.text, padding: '3px 10px',
      borderRadius: 6, fontSize: 11, fontWeight: 700,
    }}>
      {c.label}
    </span>
  )
}

// ────────────────────────────────────────────────────────
// Tab content components
// ────────────────────────────────────────────────────────

function FingerprinterTab({ data }) {
  if (!data || data.status !== 'evaluated') {
    return <NotTrainedMessage model="Siamese Fingerprinter" script="scripts/train_fingerprinter.py" />
  }

  const fpr = data.false_positive_rate || 0
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        <MetricCard label="Precision" value={(data.precision * 100).toFixed(1)} suffix="%" color="var(--accent)" />
        <MetricCard label="Recall" value={(data.recall * 100).toFixed(1)} suffix="%" color="#22c55e" />
        <MetricCard label="F1 Score" value={(data.f1 * 100).toFixed(1)} suffix="%" color="var(--accent-2)" />
        <MetricCard label="AUC-ROC" value={(data.auc * 100).toFixed(1)} suffix="%" color="#f59e0b" />
        <MetricCard label="FP Rate" value={(fpr * 100).toFixed(2)} suffix="%" warning={fpr > FPR_THRESHOLD} />
      </div>

      {data.optimal_threshold && (
        <div style={{ ...cardStyle, marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
            Optimal Threshold
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--accent)', fontFamily: 'JetBrains Mono, monospace' }}>
            {data.optimal_threshold.toFixed(2)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Threshold that maximizes F1 score on the test set.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <MatrixImage model="fingerprinter" alt="Fingerprinter Confusion Matrix" />
        <MatrixImage model="fingerprinter_threshold" alt="Threshold Sweep" />
      </div>
    </div>
  )
}

function ClassifierTab({ data }) {
  if (!data || data.status !== 'evaluated') {
    return <NotTrainedMessage model="IndicBERT Scam Classifier" script="scripts/train_classifier.py" />
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        <MetricCard label="Accuracy" value={(data.accuracy * 100).toFixed(1)} suffix="%" color="var(--accent)" />
        <MetricCard label="Macro F1" value={(data.macro_f1 * 100).toFixed(1)} suffix="%" color="#22c55e" />
        <MetricCard label="Weighted F1" value={(data.weighted_f1 * 100).toFixed(1)} suffix="%" color="var(--accent-2)" />
      </div>

      {/* Per-class breakdown table */}
      {data.per_class && (
        <div style={{ ...cardStyle, marginBottom: 20, overflowX: 'auto' }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Per-Class Breakdown</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 700 }}>Category</th>
                <th style={{ textAlign: 'right', padding: '6px 8px' }}>Precision</th>
                <th style={{ textAlign: 'right', padding: '6px 8px' }}>Recall</th>
                <th style={{ textAlign: 'right', padding: '6px 8px' }}>F1</th>
                <th style={{ textAlign: 'right', padding: '6px 8px' }}>Support</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.per_class).map(([cat, metrics]) => (
                <tr key={cat} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '6px 8px', fontWeight: 600 }}>{cat}</td>
                  <td style={{ textAlign: 'right', padding: '6px 8px', fontFamily: 'JetBrains Mono, monospace' }}>
                    {(metrics.precision * 100).toFixed(1)}%
                  </td>
                  <td style={{ textAlign: 'right', padding: '6px 8px', fontFamily: 'JetBrains Mono, monospace' }}>
                    {(metrics.recall * 100).toFixed(1)}%
                  </td>
                  <td style={{ textAlign: 'right', padding: '6px 8px', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
                    {(metrics.f1 * 100).toFixed(1)}%
                  </td>
                  <td style={{ textAlign: 'right', padding: '6px 8px', color: 'var(--text-muted)' }}>
                    {metrics.support}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Most confused pairs */}
      {data.most_confused_pairs?.length > 0 && (
        <div style={{ ...cardStyle, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Top Confused Pairs</div>
          {data.most_confused_pairs.map((pair, i) => (
            <div key={i} style={{
              fontSize: 12, padding: '4px 0', color: 'var(--text-secondary)',
              borderBottom: i < data.most_confused_pairs.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              {pair}
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <MatrixImage model="classifier_counts" alt="Raw Counts Matrix" />
        <MatrixImage model="classifier_recall" alt="Recall Normalized Matrix" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <MatrixImage model="classifier_precision" alt="Precision Normalized Matrix" />
        <MatrixImage model="classifier_calibration" alt="Calibration Plot" />
      </div>
    </div>
  )
}

function DeepfakeTab({ data }) {
  if (!data || data.status !== 'evaluated') {
    return <NotTrainedMessage model="EfficientNet-B4 Deepfake Detector" script="scripts/train_deepfake.py" />
  }

  const fpr = data.false_positive_rate || 0
  const fnr = data.false_negative_rate || 0

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        <MetricCard label="AUC-ROC" value={(data.auc_roc * 100).toFixed(1)} suffix="%" color="var(--accent)" />
        <MetricCard label="FP Rate" value={(fpr * 100).toFixed(2)} suffix="%"
          warning={fpr > FPR_THRESHOLD}
        />
        <MetricCard label="FN Rate" value={(fnr * 100).toFixed(2)} suffix="%" color="#f59e0b" />
        <MetricCard label="Threshold" value={data.recommended_threshold?.toFixed(2) || '0.50'} color="var(--accent-2)" />
      </div>

      {/* Law enforcement warning */}
      <div style={{
        ...cardStyle, marginBottom: 20,
        background: fpr > FPR_THRESHOLD ? '#fef2f210' : 'var(--bg-secondary)',
        borderColor: fpr > FPR_THRESHOLD ? '#ef444440' : 'var(--border)',
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: '#ef4444' }}>
          ⚠️ Law Enforcement Impact
        </div>
        <div style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-secondary)' }}>
          <strong>False Positive ({(fpr * 100).toFixed(2)}%)</strong> — Risk of flagging legitimate content as deepfake.
          This is the most dangerous error for law enforcement — risk of wrongful content flagging.<br />
          <strong>False Negative ({(fnr * 100).toFixed(2)}%)</strong> — Risk of missing actual deepfake content.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <MatrixImage model="deepfake" alt="Deepfake Confusion Matrix" />
        <MatrixImage model="deepfake_roc" alt="ROC Curve" />
      </div>
    </div>
  )
}

function DecisionTab({ data }) {
  if (!data || data.status !== 'evaluated') {
    return <NotTrainedMessage model="Decision Scoring Engine" script="scripts/evaluate_all_models.py" />
  }

  const binary = data.binary_collapse || {}
  const fpr = binary.false_positive_rate || 0

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        <MetricCard label="Precision" value={((binary.precision || 0) * 100).toFixed(1)} suffix="%" color="var(--accent)" />
        <MetricCard label="Recall" value={((binary.recall || 0) * 100).toFixed(1)} suffix="%" color="#22c55e" />
        <MetricCard label="F1 Score" value={((binary.f1 || 0) * 100).toFixed(1)} suffix="%" color="var(--accent-2)" />
        <MetricCard label="FP Rate" value={(fpr * 100).toFixed(2)} suffix="%" warning={fpr > FPR_THRESHOLD} />
      </div>

      {/* Decision distribution */}
      {data.decision_distribution && (
        <div style={{ ...cardStyle, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>Decision Distribution</div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {Object.entries(data.decision_distribution).map(([decision, count]) => {
              const colors = {
                IGNORE: '#75726a', MONITOR: '#f59e0b', INVESTIGATE: 'var(--accent)',
                ESCALATE: '#f97316', BLOCK: '#ef4444',
              }
              return (
                <div key={decision} style={{ textAlign: 'center' }}>
                  <div style={{
                    fontSize: 24, fontWeight: 800, color: colors[decision] || '#888',
                    fontFamily: 'JetBrains Mono, monospace',
                  }}>
                    {count}
                  </div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>
                    {decision}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Critical errors */}
      {data.critical_error_count > 0 && (
        <div style={{
          ...cardStyle, marginBottom: 20,
          background: '#fef2f210', borderColor: '#ef444440',
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: '#ef4444' }}>
            ⚠️ Critical Errors: {data.critical_error_count}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            Legitimate channels incorrectly classified as BLOCK or ESCALATE
          </div>
          {(data.critical_errors || []).map((err, i) => (
            <div key={i} style={{
              fontSize: 12, padding: '4px 0', color: 'var(--text-secondary)',
              borderBottom: '1px solid var(--border)',
            }}>
              @{err.channel} → {err.predicted} (score: {err.score?.toFixed(1)})
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <MatrixImage model="decision_5class" alt="5-Class Decision Matrix" />
        <MatrixImage model="decision_binary" alt="Binary BLOCK/NOT Matrix" />
      </div>
    </div>
  )
}

function NotTrainedMessage({ model, script }) {
  return (
    <div style={{ ...cardStyle, textAlign: 'center', padding: 60 }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🔧</div>
      <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{model}</div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 400, margin: '0 auto' }}>
        This model has not been trained or evaluated yet.
        Run the training script to generate evaluation outputs:
      </div>
      <code style={{
        display: 'inline-block', marginTop: 12, padding: '8px 16px',
        background: 'var(--bg-primary)', borderRadius: 8,
        fontSize: 12, color: 'var(--accent)',
      }}>
        python {script}
      </code>
    </div>
  )
}

// ────────────────────────────────────────────────────────
// Main component
// ────────────────────────────────────────────────────────

export default function ModelEvaluation() {
  const [activeTab, setActiveTab] = useState('fingerprinter')
  const [evalData, setEvalData] = useState(null)
  const [lastRun, setLastRun] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      const [summary, runInfo] = await Promise.all([
        api.getEvalSummary(),
        api.getEvalLastRun(),
      ])
      setEvalData(summary)
      setLastRun(runInfo)
      setLoading(false)
    }
    fetchData()
  }, [])

  function getModelData(tabId) {
    if (!evalData?.models) return null
    const map = {
      fingerprinter: 'Siamese Fingerprinter',
      classifier: 'IndicBERT Scam Classifier',
      deepfake: 'EfficientNet-B4 Deepfake Detector',
      decision: 'Decision Scoring Engine',
    }
    return evalData.models.find(m => m.model_name === map[tabId]) || null
  }

  const anyHighFPR = evalData?.summary?.any_high_fpr

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>
            📊 Model Performance
          </h1>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            Evaluation metrics, confusion matrices, and operational risk assessment
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {lastRun?.last_run && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Last evaluated: {new Date(lastRun.last_run).toLocaleString()}
            </div>
          )}
          {evalData?.summary && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {evalData.summary.evaluated}/{evalData.summary.total_models} models evaluated
              {anyHighFPR && (
                <span style={{
                  background: '#ef444420', color: '#ef4444', padding: '1px 6px',
                  borderRadius: 4, marginLeft: 8, fontSize: 10, fontWeight: 700,
                }}>
                  ⚠️ HIGH FPR
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 4, marginBottom: 20,
        background: 'var(--bg-secondary)', borderRadius: 10,
        padding: 4, border: '1px solid var(--border)',
      }}>
        {TABS.map(tab => {
          const isActive = activeTab === tab.id
          const model = getModelData(tab.id)
          const hasHighFPR = model?.false_positive_rate > FPR_THRESHOLD ||
            model?.binary_collapse?.false_positive_rate > FPR_THRESHOLD

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                flex: 1,
                padding: '10px 16px',
                border: 'none',
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: isActive ? 700 : 500,
                background: isActive ? 'var(--accent)' : 'transparent',
                color: isActive ? '#121211' : 'var(--text-secondary)',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                position: 'relative',
              }}
            >
              <span>{tab.icon}</span> {tab.label}
              {model?.status === 'evaluated' && (
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: hasHighFPR ? '#ef4444' : '#22c55e',
                  display: 'inline-block',
                }} />
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {loading ? (
        <div style={{ ...cardStyle, textAlign: 'center', padding: 60 }}>
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading evaluation data...</div>
        </div>
      ) : (
        <div className="fade-in" key={activeTab}>
          {activeTab === 'fingerprinter' && <FingerprinterTab data={getModelData('fingerprinter')} />}
          {activeTab === 'classifier' && <ClassifierTab data={getModelData('classifier')} />}
          {activeTab === 'deepfake' && <DeepfakeTab data={getModelData('deepfake')} />}
          {activeTab === 'decision' && <DecisionTab data={getModelData('decision')} />}
        </div>
      )}
    </div>
  )
}
