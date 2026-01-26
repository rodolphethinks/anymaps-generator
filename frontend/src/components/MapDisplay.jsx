import './MapDisplay.css'

function MapDisplay({ selectedImage, status }) {
  const isGenerating = status.status === 'preparing' || status.status === 'rendering'

  return (
    <div className="map-display">
      <h2>Current Map</h2>
      
      <div className="display-container">
        {isGenerating ? (
          <div className="generating-state">
            <div className="spinner"></div>
            <p className="status-text">{status.message}</p>
          </div>
        ) : selectedImage ? (
          <div className="image-container">
            <img 
              src={`/api/image/${selectedImage}`} 
              alt="Generated map"
              className="map-image"
            />
            <div className="image-label">
              {selectedImage.replace('_render.png', '')}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
              <circle cx="12" cy="10" r="3"></circle>
            </svg>
            <p>No map generated yet</p>
            <p className="hint">Fill in the form and click Generate Map</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default MapDisplay
