import { useState, useRef } from 'react'


export default function Analyze() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('ocr')
  const fileRef = useRef()

  function handleFile(e) {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setResult(null)
    const reader = new FileReader()
    reader.onload = () => setPreview(reader.result)
    reader.readAsDataURL(f)
  }

  const [error, setError] = useState(null)

  async function handleAnalyze() {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/analyze/image', { method: 'POST', body: form })
      if (res.ok) {
        setResult(await res.json())
        setActiveTab('ocr')
      } else {
        const errText = await res.text().catch(() => '')
        console.error(`Analysis API error: HTTP ${res.status}`, errText)
        setError(`Analysis failed (HTTP ${res.status}). Using demo data for preview.`)
        setResult(demoResult())
      }
    } catch (e) {
      console.error('Analysis API unreachable:', e)
      setError('Backend unreachable. Using demo data for preview.')
      setResult(demoResult())
    }
    setLoading(false)
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>🔍 Analyze Content</h2>
          <p className="subtitle">Upload an image for OCR + classification + deepfake detection</p>
        </div>
      </div>

      {/* Upload zone */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div>
          <div className="upload-zone" onClick={() => fileRef.current?.click()}>
            {preview ? (
              <img src={preview} alt="Preview" style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 8 }} />
            ) : (
              <>
                <div className="icon">📁</div>
                <div className="text">Drop scam image or click to upload</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>PNG, JPG, WEBP — Max 10MB</div>
              </>
            )}
          </div>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleFile} style={{ display: 'none' }} />
          <button className="btn btn-primary" onClick={handleAnalyze} disabled={!file || loading}
            style={{ width: '100%', marginTop: 12, justifyContent: 'center' }}>
            {loading ? '⏳ Analyzing...' : '🔍 Run Full Analysis'}
          </button>
          {error && (
            <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(255,140,0,0.15)', border: '1px solid rgba(255,140,0,0.3)', borderRadius: 8, fontSize: 12, color: '#ffaa33' }}>
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Quick result summary */}
        <div>
          {result ? (
            <div className="card" style={{ height: '100%' }}>
              <h3 style={{ marginBottom: 16 }}>⚡ Analysis Summary</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <SummaryRow label="Category" value={result.classification?.category || 'Pending'} />
                <SummaryRow label="Confidence" value={`${Math.round((result.classification?.confidence || 0) * 100)}%`} />
                <SummaryRow label="Severity" value={result.classification?.severity || 'N/A'}
                  badge={result.classification?.severity?.toLowerCase()} />
                <SummaryRow label="IT Act" value={result.classification?.it_act_section || 'N/A'} />
                <SummaryRow label="Image Type" value={result.ocr?.image_type || 'N/A'} />
                <SummaryRow label="Deepfake" value={result.deepfake?.is_suspected ? '⚠️ SUSPECTED' : '✅ Clean'} />
                <SummaryRow label="Phones Found" value={result.ocr?.entities?.phones?.length || 0} />
                <SummaryRow label="UPIs Found" value={result.ocr?.entities?.upi_ids?.length || 0} />
              </div>
            </div>
          ) : (
            <div className="card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🛡️</div>
                <div>Upload an image to begin analysis</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detailed results with tabs */}
      {result && (
        <div className="card">
          <div className="tabs">
            {['ocr', 'classify', 'deepfake', 'entities', 'legal'].map(tab => (
              <button key={tab} className={`tab ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}>
                {tab === 'ocr' ? '👁️ OCR' : tab === 'classify' ? '🧠 Classification' :
                  tab === 'deepfake' ? '🎭 Deepfake' : tab === 'entities' ? '📋 Entities' : '⚖️ Legal'}
              </button>
            ))}
          </div>

          {activeTab === 'ocr' && <OCRTab data={result.ocr} />}
          {activeTab === 'classify' && <ClassifyTab data={result.classification} />}
          {activeTab === 'deepfake' && <DeepfakeTab data={result.deepfake} />}
          {activeTab === 'entities' && <EntitiesTab data={result.ocr?.entities} />}
          {activeTab === 'legal' && <LegalTab data={result.classification} />}
        </div>
      )}
    </div>
  )
}

function SummaryRow({ label, value, badge }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>{label}</span>
      {badge ? (
        <span className={`badge badge-${badge}`}>{value}</span>
      ) : (
        <span style={{ fontSize: 13, fontWeight: 600 }}>{value}</span>
      )}
    </div>
  )
}

function OCRTab({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>No OCR data</p>
  return (
    <div>
      <div className="grid-2">
        <div>
          <h4 style={{ marginBottom: 8, fontSize: 14 }}>📝 Extracted Text</h4>
          <div className="log-feed" style={{ minHeight: 200 }}>
            <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', fontSize: 12 }}>
              {data.raw_text || 'No text extracted'}
            </pre>
          </div>
        </div>
        <div>
          <h4 style={{ marginBottom: 8, fontSize: 14 }}>📊 OCR Metadata</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <MetaRow label="Engine" value={data.engine_used} />
            <MetaRow label="Confidence" value={`${Math.round((data.confidence || 0) * 100)}%`} />
            <MetaRow label="Language" value={data.language} />
            <MetaRow label="Image Type" value={data.image_type} />
            <MetaRow label="Regions Found" value={data.regions_found} />
            <MetaRow label="Corrections" value={data.corrections_applied} />
            <MetaRow label="Time" value={`${data.processing_time_ms}ms`} />
          </div>
        </div>
      </div>
    </div>
  )
}

function ClassifyTab({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>No classification data</p>
  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div className="card-glass" style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Primary Category</div>
          <div style={{ fontSize: 18, fontWeight: 800 }}>{data.category}</div>
        </div>
        <div className="card-glass" style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Confidence</div>
          <div style={{ fontSize: 18, fontWeight: 800 }}>{Math.round((data.confidence || 0) * 100)}%</div>
        </div>
        <div className="card-glass" style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Severity</div>
          <span className={`badge badge-${data.severity?.toLowerCase()}`}>{data.severity}</span>
        </div>
      </div>
      {data.scam_indicators?.length > 0 && (
        <div>
          <h4 style={{ fontSize: 14, marginBottom: 8 }}>🚩 Scam Indicators</h4>
          {data.scam_indicators.map((ind, i) => (
            <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
              • {ind}
            </div>
          ))}
        </div>
      )}
      {data.explanation && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: 14, marginBottom: 8 }}>📋 Explanation</h4>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{data.explanation}</pre>
        </div>
      )}
    </div>
  )
}

function DeepfakeTab({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>No deepfake data</p>
  return (
    <div className="grid-2">
      <div>
        <h4 style={{ fontSize: 14, marginBottom: 12 }}>🎭 Detection Result</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <MetaRow label="Probability" value={`${Math.round((data.deepfake_probability || 0) * 100)}%`} />
          <MetaRow label="Suspected" value={data.is_suspected ? '⚠️ YES' : '✅ No'} />
          <MetaRow label="Type" value={data.deepfake_type || 'N/A'} />
          <MetaRow label="Target" value={data.target_person_type || 'N/A'} />
          <MetaRow label="Use Case" value={data.use_case_suspected || 'N/A'} />
          <MetaRow label="Faces" value={data.face_count || 0} />
          <MetaRow label="Model" value={data.model_used} />
        </div>
      </div>
      <div>
        <h4 style={{ fontSize: 14, marginBottom: 12 }}>📋 Indicators</h4>
        {(data.manipulation_indicators || []).map((ind, i) => (
          <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '4px 0' }}>• {ind}</div>
        ))}
        {data.celebrities_detected?.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <h4 style={{ fontSize: 14, marginBottom: 8 }}>🌟 Celebrities Detected</h4>
            {data.celebrities_detected.map((c, i) => (
              <span key={i} className="badge badge-critical" style={{ margin: 4 }}>{c}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function EntitiesTab({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>No entities</p>
  return (
    <div>
      {data.phones?.length > 0 && (
        <EntitySection label="📱 Phone Numbers" items={data.phones} className="entity-phone" />
      )}
      {data.upi_ids?.length > 0 && (
        <EntitySection label="💳 UPI IDs" items={data.upi_ids} className="entity-upi" />
      )}
      {data.urls?.length > 0 && (
        <EntitySection label="🔗 URLs" items={data.urls} className="entity-url" />
      )}
      {data.telegram_links?.length > 0 && (
        <EntitySection label="✈️ Telegram" items={data.telegram_links} className="entity-telegram" />
      )}
      {data.whatsapp_groups?.length > 0 && (
        <EntitySection label="💬 WhatsApp Groups" items={data.whatsapp_groups} className="entity-url" />
      )}
      {data.investment_promises?.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: 14, marginBottom: 8 }}>💰 Investment Promises</h4>
          {data.investment_promises.map((p, i) => (
            <div key={i} className="pattern-alert" style={{ animation: 'none' }}>
              <span className="alert-icon">⚠️</span>
              <span className="alert-text">{p}</span>
            </div>
          ))}
        </div>
      )}
      {(!data.phones?.length && !data.upi_ids?.length && !data.urls?.length) && (
        <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>No entities detected</p>
      )}
    </div>
  )
}

function EntitySection({ label, items, className }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h4 style={{ fontSize: 14, marginBottom: 8 }}>{label}</h4>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 0 }}>
        {items.map((item, i) => (
          <span key={i} className={`entity-box ${className}`}>{item}</span>
        ))}
      </div>
    </div>
  )
}

function LegalTab({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)' }}>No legal mapping</p>
  return (
    <div>
      <div className="card-glass" style={{ marginBottom: 16 }}>
        <h4 style={{ fontSize: 14, marginBottom: 12 }}>⚖️ Applicable Legal Sections</h4>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)' }}>{data.it_act_section || 'N/A'}</p>
      </div>
      {data.recommended_action && (
        <div>
          <h4 style={{ fontSize: 14, marginBottom: 8 }}>👮 Recommended Actions</h4>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            {data.recommended_action}
          </pre>
        </div>
      )}
      {data.victim_profile && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: 14, marginBottom: 8 }}>🎯 Victim Profile</h4>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{data.victim_profile}</p>
        </div>
      )}
    </div>
  )
}

function MetaRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600 }}>{value}</span>
    </div>
  )
}

function demoResult() {
  return {
    ocr: {
      raw_text: '🔥 GUARANTEED 300% RETURN in 7 days!\nInvest ₹5000 and get ₹20,000 back.\nCall: 98765XXXXX\nUPI: scammer@paytm\nJoin Telegram: t.me/investtips_vip\nPakka munafa! Zero risk!',
      confidence: 0.87, language: 'HINGLISH', engine_used: 'tesseract',
      image_type: 'DESIGNED_GRAPHIC', regions_found: 4, corrections_applied: 2,
      processing_time_ms: 342,
      entities: {
        phones: ['+91-98765XXXXX'], upi_ids: ['scammer@paytm'],
        urls: [], telegram_links: ['t.me/investtips_vip'],
        whatsapp_groups: [], investment_promises: ['GUARANTEED 300% RETURN in 7 days', 'Invest ₹5000 and get ₹20,000'],
        bank_accounts: [], ifsc_codes: [], amounts: ['₹5000', '₹20000'],
      },
    },
    classification: {
      category: 'Investment Scam', confidence: 0.92, severity: 'HIGH',
      it_act_section: 'IT Act §66D + IPC §420 + SEBI Act §12A',
      scam_indicators: ['Contains "guaranteed return"', 'Contains "double money"', 'Contains UPI/Telegram links'],
      victim_profile: 'Middle-aged adults (30-55), new investors, retirees seeking income',
      recommended_action: 'Freeze UPI IDs and bank accounts\nFile FIR under IT Act §66D\nReport to SEBI\nSubmit to I4C',
      explanation: 'This content classified as Investment Scam. Contains guaranteed return promises and UPI collection.',
    },
    deepfake: {
      deepfake_probability: 0.15, is_suspected: false, deepfake_type: 'unknown',
      target_person_type: 'unknown', use_case_suspected: 'other',
      manipulation_indicators: ['No significant manipulation indicators found'],
      face_count: 0, model_used: 'heuristic', celebrities_detected: [],
    },
  }
}
