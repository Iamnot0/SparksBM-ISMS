/**
 * TypeScript types for ISMS operations
 */

export type ISMSObjectType = 
  | 'scope' 
  | 'asset' 
  | 'person' 
  | 'process' 
  | 'incident' 
  | 'document' 
  | 'control' 
  | 'scenario'

export type ISMSOperation = 
  | 'list' 
  | 'create' 
  | 'get' 
  | 'update' 
  | 'delete' 
  | 'analyze'

export type ISMSReportType = 
  | 'inventory-of-assets' 
  | 'statement-of-applicability' 
  | 'risk-assessment'

export interface ISMSOperationRequest {
  operation: ISMSOperation
  objectType: ISMSObjectType
  name?: string
  id?: string
  field?: string
  value?: string
  sessionId: string
}

export interface ISMSReportRequest {
  reportType: ISMSReportType
  scopeIds?: string[]
  sessionId: string
}

export interface ISMSResponse {
  status: 'success' | 'error'
  result?: string | {
    type: 'table' | 'object_detail'
    title?: string
    columns?: string[]
    data?: any[]
    [key: string]: any
  }
  error?: string
  dataType?: 'table' | 'object_detail'
}

