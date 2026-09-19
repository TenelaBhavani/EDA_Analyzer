import { useEffect, useRef, useState } from 'react'
import { Bell, BrainCircuit, ChevronLeft, ChevronRight, FileBarChart, LayoutDashboard, Menu, MessageSquare, Search, Upload, X } from 'lucide-react'
import Plot from 'react-plotly.js'
import type { Data } from 'plotly.js'
import './App.css'

type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
}

type DatasetUploadResponse = {
  dataset_id: string
  filename: string
  rows: number
  columns: number
  column_names: string[]
  column_metadata: { name: string; dtype: string }[]
  uploaded_at: string
  status: string
  message: string
}

type DatasetListResponse = { datasets: DatasetUploadResponse[] }

type PlotType = 'bar' | 'pie' | 'histogram' | 'box' | 'distribution' | 'line' | 'scatter'
type DatasetDataResponse = { column_names: string[]; rows: Record<string, unknown>[] }
type AssistantMessageResponse = { answer: string }

const GRAPH_ROW_LIMIT = 5000

const plotTypes: { value: PlotType; label: string; columns: number }[] = [
  { value: 'bar', label: 'Bar chart', columns: 1 },
  { value: 'pie', label: 'Pie chart', columns: 1 },
  { value: 'histogram', label: 'Histogram', columns: 1 },
  { value: 'box', label: 'Box plot', columns: 1 },
  { value: 'distribution', label: 'Distribution', columns: 1 },
  { value: 'line', label: 'Line chart', columns: 2 },
  { value: 'scatter', label: 'Scatter plot', columns: 2 },
]

function numericValues(rows: Record<string, unknown>[], column: string) {
  return rows.map((row) => Number(row[column])).filter((value) => Number.isFinite(value))
}

function frequencyValues(rows: Record<string, unknown>[], column: string) {
  const counts = new Map<string, number>()
  rows.forEach((row) => {
    const value = row[column]
    if (value !== null && value !== undefined && String(value).trim()) counts.set(String(value), (counts.get(String(value)) ?? 0) + 1)
  })
  return [...counts.entries()].sort((left, right) => right[1] - left[1]).slice(0, 40)
}

function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [chatOpen, setChatOpen] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showAllAnalyses, setShowAllAnalyses] = useState(false)
  const [datasets, setDatasets] = useState<DatasetUploadResponse[]>([])
  const [datasetsLoading, setDatasetsLoading] = useState(true)
  const [datasetsError, setDatasetsError] = useState<string | null>(null)
  const [uploadedDataset, setUploadedDataset] = useState<DatasetUploadResponse | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [plotType, setPlotType] = useState<PlotType>('bar')
  const [selectedColumns, setSelectedColumns] = useState<string[]>([])
  const [plotData, setPlotData] = useState<DatasetDataResponse | null>(null)
  const [plotError, setPlotError] = useState<string | null>(null)
  const [generatingPlot, setGeneratingPlot] = useState(false)
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', text: 'I have reviewed your latest analyses. What would you like to explore?' },
  ])
  const [draft, setDraft] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const visibleDatasets = showAllAnalyses ? datasets : datasets.slice(0, 3)

  useEffect(() => {
    async function loadDatasets() {
      try {
        const response = await fetch('http://localhost:8000/api/datasets')
        const payload = await response.json() as DatasetListResponse | { detail?: string }
        if (!response.ok) throw new Error('detail' in payload && payload.detail ? payload.detail : 'Dataset history could not be loaded.')
        setDatasets((payload as DatasetListResponse).datasets)
      } catch (error) {
        setDatasetsError(error instanceof Error ? error.message : 'Dataset history could not be loaded.')
      } finally {
        setDatasetsLoading(false)
      }
    }
    void loadDatasets()
  }, [])

  async function submitMessage(text: string) {
    const trimmed = text.trim()
    if (!trimmed || assistantLoading) return
    setDraft('')
    setMessages((current) => [...current, { role: 'user', text: trimmed }])
    setAssistantLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/assistant/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: trimmed,
          dataset_id: uploadedDataset?.dataset_id,
          plot_type: plotType,
          selected_columns: selectedColumns,
          graph_generated: plotData !== null,
          graph_row_limit: GRAPH_ROW_LIMIT,
        }),
      })
      const payload = await response.json() as AssistantMessageResponse | { detail?: string }
      if (!response.ok) throw new Error('detail' in payload && payload.detail ? payload.detail : 'The assistant could not answer right now.')
      setMessages((current) => [...current, { role: 'assistant', text: (payload as AssistantMessageResponse).answer }])
    } catch (error) {
      setMessages((current) => [...current, { role: 'assistant', text: error instanceof Error ? error.message : 'The assistant could not answer right now.' }])
    } finally {
      setAssistantLoading(false)
    }
  }

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadError(null)
    setUploadedDataset(null)
    setPlotData(null)
    setSelectedColumns([])
    setPlotError(null)
    event.target.value = ''

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('http://localhost:8000/api/datasets/upload', {
        method: 'POST',
        body: formData,
      })
      const payload = await response.json() as DatasetUploadResponse | { detail?: string }
      if (!response.ok) {
        throw new Error('detail' in payload && payload.detail ? payload.detail : 'The dataset could not be uploaded.')
      }
      const dataset = payload as DatasetUploadResponse
      setUploadedDataset(dataset)
      setDatasets((current) => [dataset, ...current.filter((item) => item.dataset_id !== dataset.dataset_id)])
      setSelectedColumns(dataset.column_names.slice(0, 1))
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'The dataset could not be uploaded.')
    } finally {
      setUploading(false)
    }
  }

  function changePlotType(nextType: PlotType) {
    setPlotType(nextType)
    setPlotData(null)
    setPlotError(null)
    setSelectedColumns((current) => current.slice(0, plotTypes.find((item) => item.value === nextType)?.columns ?? 1))
  }

  async function generatePlot() {
    if (!uploadedDataset || selectedColumns.length !== (plotTypes.find((item) => item.value === plotType)?.columns ?? 1)) return
    setGeneratingPlot(true)
    setPlotError(null)
    try {
      const response = await fetch(`http://localhost:8000/api/datasets/${uploadedDataset.dataset_id}/data`)
      const payload = await response.json() as DatasetDataResponse | { detail?: string }
      if (!response.ok) throw new Error('detail' in payload && payload.detail ? payload.detail : 'The graph data could not be loaded.')
      setPlotData(payload as DatasetDataResponse)
    } catch (error) {
      setPlotError(error instanceof Error ? error.message : 'The graph could not be generated.')
    } finally {
      setGeneratingPlot(false)
    }
  }

  const selectedPlot = plotTypes.find((item) => item.value === plotType)
  const numericColumns = uploadedDataset?.column_metadata.filter((column) => /int|float|double|number|decimal/i.test(column.dtype)).map((column) => column.name) ?? []
  const availableColumns = selectedPlot?.columns === 2 ? numericColumns : uploadedDataset?.column_names ?? []
  const figure = plotData && selectedColumns.length > 0 ? (() => {
    const [firstColumn, secondColumn] = selectedColumns
    if (plotType === 'bar' || plotType === 'pie') {
      const numericColumnValues = numericValues(plotData.rows, firstColumn)
      if (numericColumnValues.length > 0 && numericColumns.includes(firstColumn)) {
        return { data: [{ type: plotType, x: plotType === 'bar' ? numericColumnValues.map((_, index) => String(index + 1)) : undefined, y: plotType === 'bar' ? numericColumnValues : undefined, labels: plotType === 'pie' ? numericColumnValues.map((_, index) => String(index + 1)) : undefined, values: plotType === 'pie' ? numericColumnValues : undefined, name: firstColumn }], title: `${selectedPlot?.label}: ${firstColumn}` }
      }
      const values = frequencyValues(plotData.rows, firstColumn)
      return { data: [{ type: plotType, x: values.map(([label]) => label), y: values.map(([, count]) => count), labels: values.map(([label]) => label), values: values.map(([, count]) => count) }], title: `${selectedPlot?.label}: ${firstColumn}` }
    }
    if (plotType === 'histogram' || plotType === 'box') {
      const values = numericValues(plotData.rows, firstColumn)
      return { data: [{ type: plotType, x: plotType === 'histogram' ? values : undefined, y: plotType === 'box' ? values : undefined, name: firstColumn }], title: `${selectedPlot?.label}: ${firstColumn}` }
    }
    if (plotType === 'distribution') {
      const values = numericValues(plotData.rows, firstColumn)
      const mean = values.reduce((sum, value) => sum + value, 0) / values.length
      const deviation = Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length) || 1
      const minimum = Math.min(...values)
      const maximum = Math.max(...values)
      const step = (maximum - minimum || 1) / 40
      const curveX = Array.from({ length: 41 }, (_, index) => minimum + index * step)
      const curveY = curveX.map((value) => Math.exp(-0.5 * ((value - mean) / deviation) ** 2) / (deviation * Math.sqrt(2 * Math.PI)))
      return { data: [{ type: 'histogram', x: values, histnorm: 'probability density', name: 'Values' }, { type: 'scatter', mode: 'lines', x: curveX, y: curveY, name: 'Density' }], title: `Distribution: ${firstColumn}` }
    }
    const pairedValues = plotData.rows
      .map((row) => ({ x: Number(row[firstColumn]), y: Number(row[secondColumn]) }))
      .filter(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))
    const x = pairedValues.map(({ x: value }) => value)
    const y = pairedValues.map(({ y: value }) => value)
    return { data: [{ type: plotType, mode: plotType === 'line' ? 'lines+markers' : 'markers', x, y, name: `${firstColumn} vs ${secondColumn}` }], title: `${selectedPlot?.label}: ${firstColumn} vs ${secondColumn}` }
  })() : null

  return (
    <div className="app-shell">
      <aside className={`sidebar ${collapsed ? 'is-collapsed' : ''} ${mobileMenuOpen ? 'is-mobile-open' : ''}`}>
        <div className="brand"><div className="brand-mark">E</div>{!collapsed && <span>EDAForge <b>AI</b></span>}</div>
        <nav>
          <p className="nav-label">Workspace</p>
          <a className="nav-item active" href="#dashboard" onClick={() => setMobileMenuOpen(false)}><LayoutDashboard size={18} />{!collapsed && 'Dashboard'}</a>
          <a className="nav-item" href="#analyses" onClick={() => setMobileMenuOpen(false)}><FileBarChart size={18} />{!collapsed && 'Analyses'}<span className="nav-count">12</span></a>
          <a className="nav-item" href="#assistant" onClick={() => { setChatOpen(true); setMobileMenuOpen(false) }}><MessageSquare size={18} />{!collapsed && 'AI Assistant'}</a>
        </nav>
        <button className="collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar">{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}</button>
      </aside>
      <main className="main-content">
        <header className="topbar"><button className="mobile-menu" aria-label="Open menu" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}><Menu size={20} /></button><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>Dashboard</strong></div><div className="top-actions"><button className="icon-button" aria-label="Search" onClick={() => document.getElementById('analyses')?.scrollIntoView({ behavior: 'smooth' })}><Search size={18} /></button><button className="icon-button" aria-label="Notifications" onClick={() => alert('No new notifications')}><Bell size={18} /><i /></button><div className="avatar" title="Alex Morgan">AM</div></div></header>
        <div className="page-content" id="dashboard">
          <section className="page-heading"><div className="product-heading"><h1>EDAForge <b>AI</b></h1><p className="subtitle">Explore your data. Discover what matters.</p></div><button className="primary-button" onClick={() => fileInputRef.current?.click()} disabled={uploading}><Upload size={17} /> {uploading ? 'Uploading...' : 'New analysis'}</button><input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" hidden onChange={handleFileChange} /></section>
          {uploadError && <div className="upload-notice upload-error" role="alert">{uploadError}</div>}
          {uploadedDataset && <div className="upload-notice" role="status"><strong>{uploadedDataset.filename}</strong> uploaded successfully. {uploadedDataset.rows} rows and {uploadedDataset.columns} columns. Dataset ID: {uploadedDataset.dataset_id}<br />Columns: {uploadedDataset.column_names.join(', ')}</div>}
          {uploadedDataset && <section className="panel visualization-panel"><div className="panel-heading"><div><p className="eyebrow">DATA VISUALIZATION</p><h2>Build a graph</h2></div><span className="chart-hint">Choose a chart and its data</span></div><div className="visualization-controls"><label>Plot type<select value={plotType} onChange={(event) => changePlotType(event.target.value as PlotType)}>{plotTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>{selectedPlot?.columns === 2 ? 'Columns' : 'Column'}<select multiple={selectedPlot?.columns === 2} value={selectedColumns} onChange={(event) => setSelectedColumns([...event.target.selectedOptions].map((option) => option.value))} size={selectedPlot?.columns === 2 ? 2 : 1}>{availableColumns.map((column) => <option key={column} value={column}>{column}</option>)}</select>{selectedPlot?.columns === 2 && <small>Select two numeric columns</small>}</label><button className="primary-button generate-button" onClick={generatePlot} disabled={generatingPlot || selectedColumns.length !== selectedPlot?.columns}>{generatingPlot ? 'Generating...' : 'Generate graph'}</button></div>{plotError && <div className="upload-notice upload-error" role="alert">{plotError}</div>}{figure && <div className="generated-chart"><Plot data={figure.data as Data[]} layout={{ title: { text: figure.title }, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', font: { color: '#dae2fd' }, autosize: true, margin: { t: 52, r: 20, b: 52, l: 52 } }} useResizeHandler style={{ width: '100%', height: '420px' }} config={{ responsive: true, displaylogo: false }} /></div>}</section>}
          <section className="panel table-panel" id="analyses"><div className="panel-heading"><div><p className="eyebrow">UPLOADED DATASETS</p><h2>Recent analyses</h2></div>{datasets.length > 3 && <button className="ghost-button" onClick={() => setShowAllAnalyses(!showAllAnalyses)}>{showAllAnalyses ? 'Show recent' : 'View all'} <ChevronRight size={15} /></button>}</div>{datasetsError && <div className="table-state table-error" role="alert">{datasetsError}</div>}{datasetsLoading && <div className="table-state">Loading uploaded datasets...</div>}{!datasetsLoading && !datasetsError && datasets.length === 0 && <div className="table-state">No datasets uploaded yet.</div>}{!datasetsLoading && !datasetsError && datasets.length > 0 && <div className="table-wrap"><table><thead><tr><th>File</th><th>Rows</th><th>Columns</th><th>Uploaded</th><th>Status</th></tr></thead><tbody>{visibleDatasets.map((dataset) => <tr key={dataset.dataset_id}><td><span className="project-icon">{dataset.filename[0]?.toUpperCase() ?? 'D'}</span><span className="filename-cell" title={dataset.filename}>{dataset.filename}</span></td><td>{dataset.rows.toLocaleString()}</td><td>{dataset.columns}</td><td>{new Date(dataset.uploaded_at).toLocaleString()}</td><td><span className="status healthy">{dataset.status}</span></td></tr>)}</tbody></table></div>}</section>
        </div>
      </main>
      {chatOpen && <aside className="chat-panel" id="assistant"><div className="chat-heading"><div><span className="ai-orb"><BrainCircuit size={17} /></span><div><strong>EDA Assistant</strong><small>{assistantLoading ? 'Analyzing data...' : 'Online · Ready to help'}</small></div></div><button onClick={() => setChatOpen(false)} aria-label="Close assistant"><X size={17} /></button></div><div className="chat-body">{messages.map((message, index) => <div className={message.role === 'assistant' ? 'assistant-message' : 'user-message'} key={`${message.role}-${index}`}>{message.text}</div>)}{assistantLoading && <div className="assistant-message assistant-loading">Analyzing your question...</div>}<div className="suggestions"><button onClick={() => void submitMessage('Explain this graph')}>Explain this graph</button><button onClick={() => void submitMessage('What is the highest value?')}>Highest value</button></div></div><form className="chat-input" onSubmit={(event) => { event.preventDefault(); void submitMessage(draft) }}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about your data or graph..." disabled={assistantLoading} /><button aria-label="Send message" type="submit" disabled={assistantLoading}><ChevronRight size={18} /></button></form></aside>}
    </div>
  )
}

export default App
