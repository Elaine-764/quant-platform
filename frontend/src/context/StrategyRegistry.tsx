import React, { createContext, useContext } from 'react'
import type { StrategyMeta, EnhancementMeta } from '../types'

type Registry = {
  strategies: StrategyMeta[]
  enhancements: EnhancementMeta[]
}

const defaultRegistry: Registry = {
  strategies: [
    {
      id: 'equity_bonds',
      title: 'Equity/Bonds Dynamic',
      endpoint: '/strategy/cross_asset/equity_bonds_dynamic',
      params: [
        { name: 'equity', type: 'asset', assetClass: 'equity' },
        { name: 'bond', type: 'asset', assetClass: 'bond' },
        { name: 'lookback', type: 'number', default: 60 },
        { name: 'bond_momentum_window', type: 'number', default: 20 },
      ],
      datasetCount: 2,
    },
    {
      id: 'delta_hedging',
      title: 'Delta Hedging',
      endpoint: '/strategy/derivatives/delta_hedging',
      params: [
        { name: 'equity', type: 'asset', assetClass: 'equity' },
        { name: 'strike', type: 'number', default: 100 },
        { name: 'days_to_expiry', type: 'number', default: 30 },
        { name: 'r', type: 'number', default: 0.04 },
        { name: 'assumed_vol', type: 'number', default: 0.2 },
        { name: 'cash_balance', type: 'number', default: 0 },
      ],
      datasetCount: 1,
    },
    {
      id: 'relative_value',
      title: 'Relative Value (Cross-Asset)',
      endpoint: '/strategy/cross_asset/relative_value',
      params: [
        { name: 'asset1', type: 'asset', assetClass: 'any' },
        { name: 'asset2', type: 'asset', assetClass: 'any' },
        { name: 'window', type: 'number', default: 60 },
        { name: 'threshold', type: 'number', default: 1.5 },
      ],
      datasetCount: 2,
    },
    {
      id: 'cointegration',
      title: 'Cointegration (Mean Reversion)',
      endpoint: '/strategy/mean_rev/cointegration',
      params: [
        { name: 'asset1', type: 'asset', assetClass: 'any' },
        { name: 'asset2', type: 'asset', assetClass: 'any' },
        { name: 'window', type: 'number', default: 60 },
        { name: 'threshold', type: 'number', default: 2.0 },
        { name: 'beta', type: 'number', default: 1.0 },
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