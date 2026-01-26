import './MapHistory.css'

function MapHistory({ history, onSelect, selectedImage }) {
  if (history.length === 0) {
    return (
      <div className="map-history">
        <h2>History</h2>
        <div className="empty-history">
          <p>No maps generated yet</p>
        </div>
      </div>
    )
  }

  return (
    <div className="map-history">
      <h2>History ({history.length})</h2>
      
      <div className="history-grid">
        {history.map((item) => (
          <div 
            key={item.filename}
            className={`history-item ${selectedImage === item.filename ? 'selected' : ''}`}
            onClick={() => onSelect(item.filename)}
          >
            <div className="thumbnail">
              <img 
                src={`/api/image/${item.filename}`} 
                alt={item.name}
              />
            </div>
            <div className="item-info">
              <h3>{item.name}</h3>
              <p className="item-date">
                {new Date(item.modified * 1000).toLocaleDateString()} 
                {' '}
                {new Date(item.modified * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default MapHistory
