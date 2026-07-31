import React from 'react'
import './App.css'
import TopBar from './components/TopBar'
import LeftPanel from './components/LeftPanel'
import RightPanel from './components/RightPanel'
import { StrategyRegistryProvider } from './context/StrategyRegistry'
import { StrategyRunProvider } from './context/StrategyRunContext'
import { ThemeProvider } from './context/ThemeContext'
import { LayoutProvider, useLayout } from './context/LayoutContext'

function AppContent() {
  const { layout } = useLayout()

  return (
    <div className="app-root">
      <TopBar />
      <main className="main-grid" data-layout={layout}>
        <LeftPanel />
        <RightPanel />
      </main>
    </div>
  )
}

function App() {
  return (
    <ThemeProvider>
      <LayoutProvider>
        <StrategyRegistryProvider>
          <StrategyRunProvider>
            <AppContent />
          </StrategyRunProvider>
        </StrategyRegistryProvider>
      </LayoutProvider>
    </ThemeProvider>
  )
}

export default App