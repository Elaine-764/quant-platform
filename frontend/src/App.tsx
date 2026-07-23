import React from 'react'
import './App.css'
import TopBar from './components/TopBar'
import LeftPanel from './components/LeftPanel'
import RightPanel from './components/RightPanel'
import { StrategyRegistryProvider } from './context/StrategyRegistry'

function App() {
  return (
    <StrategyRegistryProvider>
      <div className="app-root">
        <TopBar />
        <main className="main-grid">
          <LeftPanel />
          <RightPanel />
        </main>
      </div>
    </StrategyRegistryProvider>
  )
}

export default App
