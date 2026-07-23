import React from 'react'
import './TopBar.css'

export default function TopBar() {
  return (
    <header className="topbar">
      <div className="title">Quant Platform</div>
      <div className="controls">
        <button className="btn">Layout</button>
        <button className="btn">Theme</button>
      </div>
    </header>
  )
}
