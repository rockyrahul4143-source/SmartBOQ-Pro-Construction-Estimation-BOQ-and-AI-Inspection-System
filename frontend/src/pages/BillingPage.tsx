import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, FileText, Loader2, CheckCircle2, Send, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'
import { formatCurrency } from '@/lib/utils'

const STATUS_COLOR: Record<string,string> = {
  draft:'bg-gray-100 text-gray-700', submitted:'bg-blue-100 text-blue-700',
  certified:'bg-green-100 text-green-700', paid:'bg-emerald-100 text-emerald-700',
}

interface BillItem {
  id:string; item_no:string; description:string; unit:string; rate:number
  boq_quantity:number; previous_quantity:number; current_quantity:number
  cumulative_quantity:number; balance_quantity:number
  current_amount:number; cumulative_amount:number; previous_amount:number
  is_heading:boolean; remarks?:string
}
interface Bill {
  id:string; project_id:string; boq_id:string; bill_number:string; status:string
  contractor_name?:string; current_amount:number; cumulative_amount:number
  previous_amount:number; deductions:number; net_payable:number
  allow_excess:boolean; items:BillItem[]; created_at:string
}

export default function BillingPage() {
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [boqId, setBoqId] = useState('')
  const [activeBill, setActiveBill] = useState<Bill|null>(null)
  const [contractor, setContractor] = useState('')
  const [deductions, setDeductions] = useState(0)
  const [allowExcess, setAllowExcess] = useState(false)
  const [editingQty, setEditingQty] = useState<Record<string,string>>({})

  const { data: projects } = useQuery({ queryKey:['projects-list'], queryFn:()=>api.get('/projects/?limit=200').then(r=>r.data.data) })
  const { data: boqList } = useQuery({
    queryKey:['boqs', projectId],
    queryFn:()=>projectId ? api.get(`/boq/project/${projectId}`).then(r=>r.data) : Promise.resolve([]),
    enabled:!!projectId,
  })
  const { data: bills, refetch:refetchBills } = useQuery({
    queryKey:['bills', projectId],
    queryFn:()=>projectId ? api.get(`/billing/project/${projectId}`).then(r=>r.data) : Promise.resolve([]),
    enabled:!!projectId,
  })
  const { data: billDetail, refetch:refetchDetail } = useQuery({
    queryKey:['bill-detail', activeBill?.id],
    queryFn:()=>activeBill ? api.get(`/billing/${activeBill.id}`).then(r=>r.data) : Promise.resolve(null),
    enabled:!!activeBill?.id,
  })

  const createBill = useMutation({
    mutationFn:()=>api.post('/billing/', { project_id:projectId, boq_id:boqId, contractor_name:contractor, deductions, allow_excess:allowExcess }),
    onSuccess:(res)=>{ setActiveBill(res.data); refetchBills(); toast.success('RA Bill created') },
    onError:(e:any)=>toast.error(e.response?.data?.detail??'Error creating bill'),
  })

  const updateQty = useMutation({
    mutationFn:({ itemId, qty }:{ itemId:string; qty:number })=>
      api.put(`/billing/${activeBill!.id}/items/${itemId}`, { current_quantity:qty }),
    onSuccess:()=>{ refetchDetail(); toast.success('Quantity updated') },
    onError:(e:any)=>toast.error(e.response?.data?.detail??'Error — check BOQ quantity limits'),
  })

  const submitBill = useMutation({
    mutationFn:()=>api.post(`/billing/${activeBill!.id}/submit`),
    onSuccess:(res)=>{ setActiveBill(res.data); refetchBills(); toast.success('Bill submitted') },
  })

  const certifyBill = useMutation({
    mutationFn:()=>api.post(`/billing/${activeBill!.id}/certify`),
    onSuccess:(res)=>{ setActiveBill(res.data); refetchBills(); toast.success('Bill certified') },
  })

  const bill: Bill|null = billDetail ?? activeBill
  const items: BillItem[] = bill?.items ?? []
  const isEditable = bill?.status === 'draft'

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2"><FileText className="h-5 w-5"/>RA Billing</h1>
        <p className="text-sm text-muted-foreground">Running Account bills — track quantities against BOQ</p>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div className="space-y-1"><Label>Project</Label>
          <Select value={projectId} onValueChange={v=>{setProjectId(v);setBoqId('');setActiveBill(null)}}>
            <SelectTrigger><SelectValue placeholder="Select project"/></SelectTrigger>
            <SelectContent>{(projects??[]).map((p:any)=><SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1"><Label>BOQ</Label>
          <Select value={boqId} onValueChange={setBoqId} disabled={!projectId}>
            <SelectTrigger><SelectValue placeholder="Select BOQ"/></SelectTrigger>
            <SelectContent>{(boqList??[]).map((b:any)=><SelectItem key={b.id} value={b.id}>{b.boq_number} — {b.title}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1"><Label>Contractor</Label>
          <Input placeholder="Contractor name" value={contractor} onChange={e=>setContractor(e.target.value)} disabled={!boqId}/>
        </div>
        <Button disabled={!boqId||createBill.isPending} onClick={()=>createBill.mutate()}>
          {createBill.isPending?<Loader2 className="h-4 w-4 animate-spin mr-1"/>:<Plus className="h-4 w-4 mr-1"/>}
          New RA Bill
        </Button>
      </div>

      {/* Bill list */}
      {(bills??[]).length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {(bills??[]).map((b:Bill)=>(
            <button key={b.id} onClick={()=>setActiveBill(b)}
              className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${activeBill?.id===b.id?'bg-primary text-white border-primary':'bg-white hover:bg-muted border-border'}`}>
              <span className="font-semibold">{b.bill_number}</span>
              <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLOR[b.status]??''}`}>{b.status}</span>
              <span className="ml-2 text-muted-foreground">{formatCurrency(b.net_payable)}</span>
            </button>
          ))}
        </div>
      )}

      {/* Bill Detail */}
      {bill && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <CardTitle className="text-base">{bill.bill_number}</CardTitle>
                <p className="text-xs text-muted-foreground">{bill.contractor_name ?? 'No contractor'}</p>
              </div>
              <div className="flex gap-2">
                {bill.status === 'draft' && (
                  <Button size="sm" variant="outline" onClick={()=>submitBill.mutate()} disabled={submitBill.isPending}>
                    <Send className="h-3 w-3 mr-1"/>Submit
                  </Button>
                )}
                {bill.status === 'submitted' && (
                  <Button size="sm" onClick={()=>certifyBill.mutate()} disabled={certifyBill.isPending}>
                    <CheckCircle2 className="h-3 w-3 mr-1"/>Certify
                  </Button>
                )}
                <Badge className={STATUS_COLOR[bill.status]}>{bill.status}</Badge>
              </div>
            </div>
            {bill.allow_excess && (
              <div className="flex items-center gap-1 text-xs text-orange-600 bg-orange-50 rounded px-2 py-1 w-fit mt-1">
                <AlertTriangle className="h-3 w-3"/>Excess quantity allowed
              </div>
            )}
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-primary text-white">
                  <tr>{[
                    'Item','Description','Unit','Rate',
                    'BOQ Qty','Prev Qty','Current Qty','Cum. Qty','Balance',
                    'Current Amt','Cum. Amt'
                  ].map(h=><th key={h} className="px-2 py-2 text-right first:text-left font-medium whitespace-nowrap">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y">
                  {items.map(item=>{
                    const pct = item.boq_quantity > 0 ? (item.cumulative_quantity / item.boq_quantity) * 100 : 0
                    return (
                      <tr key={item.id} className={`hover:bg-muted/20 ${item.is_heading?'bg-muted/40 font-semibold':''}`}>
                        <td className="px-2 py-1.5 text-left">{item.item_no}</td>
                        <td className="px-2 py-1.5 text-left max-w-xs">
                          <p className={item.is_heading?'font-semibold':''}>{item.description}</p>
                          {!item.is_heading && pct > 0 && (
                            <div className="mt-1 flex items-center gap-1">
                              <div className="flex-1 bg-muted rounded-full h-1.5 max-w-20">
                                <div className={`h-1.5 rounded-full ${pct>=100?'bg-red-500':pct>=75?'bg-orange-400':'bg-green-400'}`} style={{width:`${Math.min(pct,100)}%`}}/>
                              </div>
                              <span className="text-muted-foreground">{pct.toFixed(0)}%</span>
                            </div>
                          )}
                        </td>
                        {item.is_heading ? (
                          <td colSpan={9}/>
                        ) : <>
                          <td className="px-2 py-1.5 text-right">{item.unit}</td>
                          <td className="px-2 py-1.5 text-right">{formatCurrency(item.rate)}</td>
                          <td className="px-2 py-1.5 text-right font-medium">{item.boq_quantity.toFixed(3)}</td>
                          <td className="px-2 py-1.5 text-right text-muted-foreground">{item.previous_quantity.toFixed(3)}</td>
                          <td className="px-2 py-1.5 text-right">
                            {isEditable ? (
                              <Input type="number" step="0.001" min="0"
                                className="h-6 text-xs w-20 text-right"
                                value={editingQty[item.id] !== undefined ? editingQty[item.id] : item.current_quantity}
                                onChange={e=>setEditingQty(q=>({...q,[item.id]:e.target.value}))}
                                onBlur={()=>{
                                  const v = parseFloat(editingQty[item.id] ?? String(item.current_quantity))
                                  if (!isNaN(v) && v !== item.current_quantity) {
                                    updateQty.mutate({itemId:item.id, qty:v})
                                  }
                                  setEditingQty(q=>{const n={...q};delete n[item.id];return n})
                                }}
                              />
                            ) : (
                              <span>{item.current_quantity.toFixed(3)}</span>
                            )}
                          </td>
                          <td className={`px-2 py-1.5 text-right font-semibold ${item.cumulative_quantity > item.boq_quantity ? 'text-red-600':''}`}>
                            {item.cumulative_quantity.toFixed(3)}
                          </td>
                          <td className="px-2 py-1.5 text-right text-muted-foreground">{item.balance_quantity.toFixed(3)}</td>
                          <td className="px-2 py-1.5 text-right font-semibold text-green-700">{formatCurrency(item.current_amount)}</td>
                          <td className="px-2 py-1.5 text-right">{formatCurrency(item.cumulative_amount)}</td>
                        </>}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Bill summary */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 p-4 bg-muted/30 border-t">
              {[
                ['Previous Bill',bill.previous_amount,'text-muted-foreground'],
                ['Current Bill',bill.current_amount,'text-blue-700'],
                ['Cumulative',bill.cumulative_amount,'text-purple-700'],
                ['Deductions',bill.deductions,'text-red-600'],
                ['Net Payable',bill.net_payable,'text-green-700 text-xl font-bold'],
              ].map(([l,v,cls])=>(
                <div key={l as string} className="text-center">
                  <p className="text-xs text-muted-foreground">{l as string}</p>
                  <p className={`font-semibold ${cls as string}`}>{formatCurrency(v as number)}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {!bill && projectId && (
        <div className="text-center py-16 text-muted-foreground">
          <FileText className="h-12 w-12 mx-auto mb-3 opacity-20"/>
          <p>Select a BOQ and create a new RA Bill</p>
        </div>
      )}
      {!projectId && (
        <div className="text-center py-16 text-muted-foreground">
          <FileText className="h-12 w-12 mx-auto mb-3 opacity-20"/>
          <p>Select a project to view and create RA bills</p>
        </div>
      )}
    </div>
  )
}
