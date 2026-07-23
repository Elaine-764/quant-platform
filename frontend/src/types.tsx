export type ParamDef = {
  name: string
  type: 'number' | 'string' | 'boolean' | 'select'
  default?: any
  options?: string[]
  description?: string
}

export type AssetClass = 'equity' | 'bond' | 'any'

export interface AssetParamMeta {
  name: string
  type: 'asset'
  assetClass: AssetClass
  default?: string
}

export interface PrimitiveParamMeta {
  name: string
  type: 'string' | 'number'
  default?: string | number
}

export type ParamMeta = AssetParamMeta | PrimitiveParamMeta

export interface StrategyMeta {
  id: string
  title: string
  endpoint: string
  params: ParamMeta[]
  datasetCount: number
}

export interface EnhancementMeta {
  id: string
  title: string
  endpoint: string
  category: 'filter' | 'position_sizer'
  params: ParamMeta[]
  datasetCount: number
}