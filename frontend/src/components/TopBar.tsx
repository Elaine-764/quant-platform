import React from 'react'
import { useTheme } from '../context/ThemeContext'
import { useLayout } from '../context/LayoutContext'
import './TopBar.css'

export default function TopBar() {
  const { theme, toggleTheme } = useTheme()
  const { layout, toggleLayout } = useLayout()

  return (
    <header className="topbar">
      <div className="title">Trading Strategies Backtest Platform</div>
      <div className="controls">
        <button className="btn" onClick={toggleLayout} title={`Layout: ${layout}`}>
          {layout === 'horizontal' ? '⊡ Horizontal' : '⊞ Vertical'}
        </button>
        <button className="btn" onClick={toggleTheme} title={`Theme: ${theme}`}>
          {theme === 'light' ? '☀️ Light' : '🌙 Dark'}
        </button>
      </div>
    </header>
  )
}
