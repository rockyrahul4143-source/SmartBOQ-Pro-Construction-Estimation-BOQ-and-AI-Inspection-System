import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, BarChart3, Loader2, Trash2, Check, X, Save } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/useToast'
import { formatCurrency } from '@/lib/utils'

const COMP_TYPES = ['material','labour','equipment']
const UNITS = ['m3','m2','m','kg','no','bag','day','hr','ltr','rft']

interface Comp { id:string; component_type:string; description:string; unit:string; quantity:number; rate:number; amount:number; sort_order:number }
interface RA {
  id:string; sor_item_id:string; title:string; unit:string
  material_total:number; labour_total:number; equipment_total:number; direct_cost:number
  wastage_pct:number; wastage_amount:number; overhead_pct:number; overhead_amount:number
  profit_pct:number; profit_amount:number; final_rate:number; components:Comp[]
}

const emptyComp = { component_type:'material', description:'', unit:'kg', quantity:0, rate:0, sort_order:0 }

export default function RateAnalysisPage() {
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [sorSearch, setSorSearch] = useState('')
  const [selectedSOR, setSelectedSOR] = useState<any>(null)
  const [activeRA, setActiveRA] = useState<RA|null>(null)
  const [comp, setComp] = useState({ ...emptyComp })
  const [pcts, setPcts] = useState({ wastage_pct:5, overhead_pct:10, profit_pct:10 })

  const { data: projects } = useQuery({ queryKey:['projects-list'], queryFn:()=>api.get('/projects/?limit=200').then(r=>r.data.data) })
  const { data: sorItems } = useQuery({
    queryKey:['sor-search', sorSearch],
    queryFn:()=>api.get('/sor/', { params:{ search:sorSearch||undefined, limit:50 }}).then(r=>r.data),
  })
  const { data: raList, refetch } = useQuery({
    queryKey:['ra-list', selectedSOR?.id],
    queryFn:()=>selectedSOR ? api.get(`/rate-analysis/sor/${selectedSOR.id}`).then(r=>r.data) : Promise.resolve([]),
    enabled:!!selectedSOR,
  })
  const { data: raDetail, refetch: refetchDetail } = useQuery({
    queryKey:['ra-detail', activeRA?.id],
    queryFn:()=>activeRA ? api.get(`/rate-analysis/${activeRA.id}`).then(r=>r.data) : Promise.resolve(null),
    enabled:!!activeRA?.id,
  })

  const createRA = useMutation({
    mutationFn:()=>api.post('/rate-analysis/', {
      sor_item_id:selectedSOR.id, title:selectedSOR.description,
      unit:selectedSOR.unit, project_id:projectId||undefined, ...pcts
    }),
    onSuccess:(res)=>{ setActiveRA(res.data); refetch(); toast.success('Rate analysis created') },
    onError:(e:any)=>toast.error(e.response?.data?.detail??'Error'),
  })

  const addComp = useMutation({
    mutationFn:()=>api.post(`/rate-analysis/${activeRA!.id}/components`, comp),
    onSuccess:()=>{ refetchDetail(); setComp({...emptyComp}); toast.success('Component added') },
    onError:(e:any)=>toast.error(e.response?.data?.detail??'Error'),
  })

  const delComp = useMutation({
    mutationFn:(cid:string)=>api.delete(`/rate-analysis/${activeRA!.id}/components/${cid}`),
    onSuccess:()=>{ refetchDetail(); toast.success('Removed') },
  })

  const updatePcts = useMutation({
    mutationFn:()=>api.put(`/rate-analysis/${activeRA!.id}`, pcts),
    onSuccess:(res)=>{ setActiveRA(res.data); refetchDetail(); toast.success('Updated') },
  })

  const ra: RA|null = raDetail ?? activeRA

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2"><BarChart3 className="h-5 w-5"/>Rate Analysis</h1>
        <p className="text-sm text-muted-foreground">Material + Labour + Equipment breakdown per BOQ item</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: SOR Item selector */}
        <div className="space-y-3">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Select SOR Item</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              <Input placeholder="Search items..." value={sorSearch} onChange={e=>setSorSearch(e.target.value)}/>
              <Select value={projectId} onValueChange={setProjectId}>
                <SelectTrigger><SelectValue placeholder="Link to project (opt.)"/></SelectTrigger>
                <SelectContent>{(projects??[]).map((p:any)=><SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>)}</SelectContent>
              </Select>
              <div className="max-h-64 overflow-y-auto space-y-1">
                {(sorItems?.data??[]).map((item:any)=>(
                  <button key={item.id} onClick={()=>{setSelectedSOR(item);setActiveRA(null)}}
                    className={`w-full text-left px-3 py-2 rounded text-xs border transition-colors ${selectedSOR?.id===item.id?'bg-primary text-white border-primary':'hover:bg-muted border-transparent'}`}>
                    <span className="font-mono mr-2">{item.item_code}</span>
                    <span className="line-clamp-1">{item.description}</span>
                    <span className="block text-right font-semibold mt-0.5">{formatCurrency(item.basic_rate)}/{item.unit}</span>
                  </button>
                ))}
              </div>
              {selectedSOR && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-xs font-semibold text-muted-foreground">Existing analyses:</p>
                  {(raList??[]).map((r:RA)=>(
                    <button key={r.id} onClick={()=>setActiveRA(r)}
                      className={`w-full text-left px-3 py-1.5 rounded text-xs border ${activeRA?.id===r.id?'bg-primary/10 border-primary':'hover:bg-muted border-transparent'}`}>
                      {r.title} — <strong>{formatCurrency(r.final_rate)}/{r.unit}</strong>
                    </button>
                  ))}
                  <Button size="sm" className="w-full" onClick={()=>createRA.mutate()} disabled={createRA.isPending}>
                    <Plus className="h-3 w-3 mr-1"/>New Analysis
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Rate analysis detail */}
        <div className="lg:col-span-2 space-y-3">
          {ra ? (
            <>
              <Card>
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-base">{ra.title}</CardTitle>
                    <p className="text-xs text-muted-foreground">Per {ra.unit}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-green-700">{formatCurrency(ra.final_rate)}</p>
                    <p className="text-xs text-muted-foreground">Final Rate / {ra.unit}</p>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Components table */}
                  <table className="w-full text-xs mb-3">
                    <thead className="bg-muted/50">
                      <tr>{['Type','Description','Unit','Qty','Rate','Amount',''].map(h=><th key={h} className="px-2 py-1.5 text-left font-medium text-muted-foreground">{h}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y">
                      {['material','labour','equipment'].map(type=>{
                        const group = (ra.components??[]).filter(c=>c.component_type===type)
                        const total = group.reduce((s,c)=>s+c.amount,0)
                        return [
                          <tr key={`h-${type}`} className="bg-muted/30">
                            <td colSpan={7} className="px-2 py-1 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                              {type} — {formatCurrency(total)}
                            </td>
                          </tr>,
                          ...group.map(c=>(
                            <tr key={c.id} className="hover:bg-muted/20">
                              <td className="px-2 py-1"></td>
                              <td className="px-2 py-1">{c.description}</td>
                              <td className="px-2 py-1">{c.unit}</td>
                              <td className="px-2 py-1 text-right">{c.quantity}</td>
                              <td className="px-2 py-1 text-right">{formatCurrency(c.rate)}</td>
                              <td className="px-2 py-1 text-right font-semibold">{formatCurrency(c.amount)}</td>
                              <td className="px-2 py-1">
                                <button onClick={()=>delComp.mutate(c.id)} className="text-destructive hover:opacity-80"><Trash2 className="h-3 w-3"/></button>
                              </td>
                            </tr>
                          ))
                        ]
                      })}
                    </tbody>
                  </table>

                  {/* Add component row */}
                  <div className="bg-muted/30 rounded p-3 space-y-2">
                    <p className="text-xs font-semibold">Add Component</p>
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                      <Select value={comp.component_type} onValueChange={v=>setComp(f=>({...f,component_type:v}))}>
                        <SelectTrigger className="h-7 text-xs"><SelectValue/></SelectTrigger>
                        <SelectContent>{COMP_TYPES.map(t=><SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                      </Select>
                      <Input className="h-7 text-xs col-span-2" placeholder="Description" value={comp.description} onChange={e=>setComp(f=>({...f,description:e.target.value}))}/>
                      <Select value={comp.unit} onValueChange={v=>setComp(f=>({...f,unit:v}))}>
                        <SelectTrigger className="h-7 text-xs"><SelectValue/></SelectTrigger>
                        <SelectContent>{UNITS.map(u=><SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                      </Select>
                      <Input type="number" className="h-7 text-xs" placeholder="Qty" value={comp.quantity||''} onChange={e=>setComp(f=>({...f,quantity:+e.target.value}))}/>
                      <Input type="number" className="h-7 text-xs" placeholder="Rate" value={comp.rate||''} onChange={e=>setComp(f=>({...f,rate:+e.target.value}))}/>
                    </div>
                    {comp.quantity > 0 && comp.rate > 0 && (
                      <p className="text-xs text-muted-foreground">{comp.quantity} × {formatCurrency(comp.rate)} = <strong>{formatCurrency(comp.quantity*comp.rate)}</strong></p>
                    )}
                    <Button size="sm" disabled={!comp.description||addComp.isPending} onClick={()=>addComp.mutate()}>
                      {addComp.isPending?<Loader2 className="h-3 w-3 animate-spin"/>:<Plus className="h-3 w-3"/>} Add
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Summary & percentages */}
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm">Cost Summary & Percentages</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    {[
                      ['Material',ra.material_total,'bg-blue-50 text-blue-700'],
                      ['Labour',ra.labour_total,'bg-green-50 text-green-700'],
                      ['Equipment',ra.equipment_total,'bg-orange-50 text-orange-700'],
                      ['Direct Cost',ra.direct_cost,'bg-muted text-foreground'],
                    ].map(([l,v,cls])=>(
                      <div key={l as string} className={`rounded-lg p-3 ${cls as string}`}>
                        <p className="text-xs opacity-70">{l as string}</p>
                        <p className="text-lg font-bold">{formatCurrency(v as number)}</p>
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    {[['Wastage %','wastage_pct'],['Overhead %','overhead_pct'],['Profit %','profit_pct']].map(([l,k])=>(
                      <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label>
                        <Input type="number" className="h-8 text-xs" value={(pcts as any)[k]}
                          onChange={e=>setPcts(p=>({...p,[k]:+e.target.value}))}/>
                      </div>
                    ))}
                  </div>
                  <Button size="sm" onClick={()=>updatePcts.mutate()} disabled={updatePcts.isPending}>
                    <Save className="h-3 w-3 mr-1"/>Update Percentages
                  </Button>
                  <div className="mt-3 pt-3 border-t space-y-1 text-sm">
                    {[
                      ['Direct Cost', ra.direct_cost],
                      [`Wastage (${ra.wastage_pct}%)`, ra.wastage_amount],
                      [`Overhead (${ra.overhead_pct}%)`, ra.overhead_amount],
                      [`Profit (${ra.profit_pct}%)`, ra.profit_amount],
                    ].map(([l,v])=>(
                      <div key={l as string} className="flex justify-between">
                        <span className="text-muted-foreground">{l as string}</span>
                        <span>{formatCurrency(v as number)}</span>
                      </div>
                    ))}
                    <div className="flex justify-between font-bold text-lg pt-1 border-t text-green-700">
                      <span>Final Rate / {ra.unit}</span>
                      <span>{formatCurrency(ra.final_rate)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
              <div className="text-center"><BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-20"/>
                <p>Select an SOR item and create a rate analysis</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
