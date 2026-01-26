import { useState, useEffect } from 'react'
import MapForm from './components/MapForm'
import MapDisplay from './components/MapDisplay'
import MapHistory from './components/MapHistory'
import './App.css'

function App() {
  const [config, setConfig] = useState(null)
  const [status, setStatus] = useState({ status: 'idle', message: '', current_file: null })
  const [history, setHistory] = useState([])
  const [selectedImage, setSelectedImage] = useState(null)

  // Load initial config
  useEffect(() => {
    fetch('/api/config')
      .then(res => res.json())
      .then(data => setConfig(data))
      .catch(err => console.error('Failed to load config:', err))
  }, [])

  // Poll status when generating
  useEffect(() => {
    if (status.status === 'preparing' || status.status === 'rendering') {
      const interval = setInterval(() => {
        fetch('/api/status')
          .then(res => res.json())
          .then(data => {
            setStatus(data)
            if (data.status === 'complete') {
              loadHistory()
              setSelectedImage(data.current_file)
            }
          })
      }, 2000)
      
      return () => clearInterval(interval)
    }
  }, [status.status])

  // Load history
  const loadHistory = () => {
    fetch('/api/history')
      .then(res => res.json())
      .then(data => setHistory(data))
      .catch(err => console.error('Failed to load history:', err))
  }

  useEffect(() => {
    loadHistory()
  }, [])

  const handleGenerate = (formData) => {
    fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setStatus({ status: 'preparing', message: 'Starting...', current_file: null })
        }
      })
      .catch(err => console.error('Failed to start generation:', err))
  }

  if (!config) return <div className="loading">Loading...</div>

  return (
    <div className="app">
      <header className="header">
        <h1>AnyMaps <span>Generator</span></h1>
        <p className="subtitle">Create beautiful relief maps from anywhere in the world</p>
      </header>

      <div className="main-content">
        <div className="left-panel">
          <MapForm 
            initialConfig={config}
            onGenerate={handleGenerate}
            status={status}
          />
        </div>

        <div className="right-panel">
          <MapDisplay 
            selectedImage={selectedImage}
            status={status}
          />
          
          <MapHistory 
            history={history}
            onSelect={setSelectedImage}
            selectedImage={selectedImage}
          />
        </div>
      </div>
    </div>
  )
}

export default App
