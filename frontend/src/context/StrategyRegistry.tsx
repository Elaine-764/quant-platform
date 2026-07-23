import React, { createContext, useContext } from 'react'
import type { StrategyMeta, EnhancementMeta } from '../types'

type Registry = {
  strategies: StrategyMeta[]
  enhancements: EnhancementMeta[]
}

const defaultRegistry: Registry = {
  // context/StrategyRegistry.tsx (relevant excerpt)
    strategies: [
    {
        id: 'equity_bonds',
        title: 'Equity/Bonds Dynamic',
        endpoint: '/strategy/cross_asset/equity_bonds',
        params: [
        { name: 'equity', type: 'asset', assetClass: 'equity' },
        { name: 'bond', type: 'asset', assetClass: 'bond' },
        { name: 'lookback', type: 'number', default: 60 },
        { name: 'bond_momentum_window', type: 'number', default: 20 },
        ],
        datasetCount: 2,
    },
    ],
    enhancements: [
    {
        id: 'vol_filter',
        title: 'Volatility Filter',
        endpoint: '/enhancements/filter/volatility',
        category: 'filter',
        params: [
        { name: 'lookback', type: 'number', default: 20 },
        { name: 'min_vol', type: 'number' },
        { name: 'max_vol', type: 'number' },
        ],
        datasetCount: 0,
    },
    {
        id: 'kelly',
        title: 'Kelly Criterion',
        endpoint: '/enhancements/position_sizer/kelly',
        category: 'position_sizer',
        params: [
        { name: 'win_rate', type: 'number', default: 0.55 },
        { name: 'avg_win', type: 'number', default: 0.02 },
        { name: 'avg_loss', type: 'number', default: 0.01 },
        { name: 'kelly_fraction', type: 'number', default: 0.25 },
        ],
        datasetCount: 0,
    },
    ],
}

const RegistryContext = createContext<Registry>(defaultRegistry)

export const StrategyRegistryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <RegistryContext.Provider value={defaultRegistry}>{children}</RegistryContext.Provider>
}

export const useRegistry = () => useContext(RegistryContext)

export default RegistryContext
