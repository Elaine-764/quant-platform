import React from 'react'
import './RightPanel.css'

function ChartPlaceholder() {
  return (
    <div className="chart-placeholder">
      <svg viewBox="0 0 600 200" className="chart-svg">
        <polyline
          fill="none"
          stroke="#60a5fa"
          strokeWidth={2}
          points="0,150 50,120 100,110 150,90 200,70 250,80 300,60 350,40 400,55 450,30 500,20 550,10 600,5"
        />
      </svg>
    </div>
  )
}

export default function RightPanel() {
  return (
    <aside className="right-panel">
      <div className="top-half">
        <div className="pane">
          <h4>Equity Curve</h4>
          <ChartPlaceholder />
          <div className="chart-controls">
            <label>
              <input type="checkbox" /> Show buy & hold
            </label>
            <label>
              <input type="checkbox" /> Regime shading
            </label>
          </div>
        </div>
        <div className="pane metrics-pane">
          <h4>Metrics</h4>
          <div className="metrics-list">
            <div>Final portfolio value: —</div>
            <div>Total return: —</div>
            <div>Sharpe: —</div>
            <div>Max drawdown: —</div>
          </div>
        </div>
      </div>

      <div className="bottom-half">
        <div className="pane">
          <h4>Robustness Tests</h4>
          <div className="tests-list">
            <div className="test-item">
              <div className="test-title">Bootstrap CI</div>
              <div className="test-actions">
                <button className="btn small">Adjust params</button>
                <button className="btn small">Rerun</button>
              </div>
            </div>
            <div className="test-item">
              <div className="test-title">Noise Injection</div>
              <div className="test-actions">
                <button className="btn small">Adjust params</button>
                <button className="btn small">Rerun</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
