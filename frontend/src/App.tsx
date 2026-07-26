import React from 'react'
import './App.css'
import TopBar from './components/TopBar'
import LeftPanel from './components/LeftPanel'
import RightPanel from './components/RightPanel'
import { StrategyRegistryProvider } from './context/StrategyRegistry'
import { StrategyRunProvider } from './context/StrategyRunContext'

function App() {
  return (
    <StrategyRegistryProvider>
      <StrategyRunProvider>
        <div className="app-root">
          <TopBar />
          <main className="main-grid">
            <LeftPanel />
            <RightPanel />
          </main>
        </div>
      </StrategyRunProvider>
    </StrategyRegistryProvider>
  )
}

export default App