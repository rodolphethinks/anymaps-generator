import { useState, useEffect } from 'react'
import './MapForm.css'

function MapForm({ initialConfig, onGenerate, status }) {
  const [locationName, setLocationName] = useState('')
  const [locationType, setLocationType] = useState('country')
  const [parentCountry, setParentCountry] = useState('')
  const [lowColor, setLowColor] = useState('#F2FAFF')
  const [highColor, setHighColor] = useState('#051480')

  useEffect(() => {
    if (initialConfig) {
      setLocationName(initialConfig.location_name || '')
      setLocationType(initialConfig.location_type || 'country')
      setParentCountry(initialConfig.parent_country || '')
      
      const colors = initialConfig.colors || {}
      if (colors.low_color) {
        setLowColor(rgbaToHex(colors.low_color))
      }
      if (colors.high_color) {
        setHighColor(rgbaToHex(colors.high_color))
      }
    }
  }, [initialConfig])

  const rgbaToHex = (rgba) => {
    const r = Math.round(rgba[0] * 255).toString(16).padStart(2, '0')
    const g = Math.round(rgba[1] * 255).toString(16).padStart(2, '0')
    const b = Math.round(rgba[2] * 255).toString(16).padStart(2, '0')
    return `#${r}${g}${b}`
  }

  const hexToRgba = (hex) => {
    const r = parseInt(hex.slice(1, 3), 16) / 255
    const g = parseInt(hex.slice(3, 5), 16) / 255
    const b = parseInt(hex.slice(5, 7), 16) / 255
    return [r, g, b, 1.0]
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    
    const formData = {
      location_name: locationName,
      location_type: locationType,
      parent_country: parentCountry || null,
      colors: {
        low_color: hexToRgba(lowColor),
        high_color: hexToRgba(highColor)
      }
    }
    
    onGenerate(formData)
  }

  const isGenerating = status.status === 'preparing' || status.status === 'rendering'

  return (
    <div className="map-form">
      <h2>Create New Map</h2>
      
      <form onSubmit={handleSubmit}>
        <div className="form-section">
          <h3>Location</h3>
          
          <div className="form-group">
            <label htmlFor="locationName">Name</label>
            <input
              id="locationName"
              type="text"
              value={locationName}
              onChange={(e) => setLocationName(e.target.value)}
              placeholder="e.g. Greece, Hérault, South Korea"
              required
              disabled={isGenerating}
            />
          </div>

          <div className="form-group">
            <label>Type</label>
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  value="country"
                  checked={locationType === 'country'}
                  onChange={(e) => setLocationType(e.target.value)}
                  disabled={isGenerating}
                />
                Country
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  value="region"
                  checked={locationType === 'region'}
                  onChange={(e) => setLocationType(e.target.value)}
                  disabled={isGenerating}
                />
                Region
              </label>
            </div>
          </div>

          {locationType === 'region' && (
            <div className="form-group">
              <label htmlFor="parentCountry">Parent Country (Optional)</label>
              <input
                id="parentCountry"
                type="text"
                value={parentCountry}
                onChange={(e) => setParentCountry(e.target.value)}
                placeholder="e.g. France, USA"
                disabled={isGenerating}
              />
            </div>
          )}
        </div>

        <div className="form-section">
          <h3>Elevation Colors</h3>
          
          <div className="color-group">
            <div className="form-group">
              <label htmlFor="lowColor">Low Elevation</label>
              <div className="color-input">
                <input
                  id="lowColor"
                  type="color"
                  value={lowColor}
                  onChange={(e) => setLowColor(e.target.value)}
                  disabled={isGenerating}
                />
                <span className="color-value">{lowColor}</span>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="highColor">High Elevation</label>
              <div className="color-input">
                <input
                  id="highColor"
                  type="color"
                  value={highColor}
                  onChange={(e) => setHighColor(e.target.value)}
                  disabled={isGenerating}
                />
                <span className="color-value">{highColor}</span>
              </div>
            </div>
          </div>

          <div className="gradient-preview">
            <div 
              className="gradient-bar"
              style={{
                background: `linear-gradient(to right, ${lowColor}, ${highColor})`
              }}
            />
            <div className="gradient-labels">
              <span>Low</span>
              <span>High</span>
            </div>
          </div>
        </div>

        <button 
          type="submit" 
          className="generate-btn"
          disabled={isGenerating || !locationName}
        >
          {isGenerating ? status.message : 'Generate Map'}
        </button>
      </form>

      {status.status === 'error' && (
        <div className="status-message error">
          {status.message}
        </div>
      )}
    </div>
  )
}

export default MapForm
