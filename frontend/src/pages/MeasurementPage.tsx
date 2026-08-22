import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Ruler, Loader2, Trash2, Edit2, Calculator, X, Check, ChevronDown } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/useToast'

interface MBItem {
  id: string; sort_order: number; is_heading: boolean; item_ref?: string
  description: string; unit?: string; length?: number; width?: number
  height?: number; nos?: number; quantity?: number; formula_display?: string
  is_manual_override: boolean; is_deduction: boolean; notes?: string
}

interface MB { id: string; mb_number: string; title: string; description?: string; items: MBItem[]; created_at: string }

const UNITS = ['m3','m2','m','kg','no','ltr','bag','point','rft']

function FormulaRow({ item }: { item: MBItem }) {
  return (
    <tr className={`border-b hover:bg-muted/20 ${item.is_heading ? 'bg-primary/5 font-semibold' : ''} ${item.is_deduction ? 'text-red-600' : ''}`}>
      <td className="px-2 py-1.5 text-xs text-muted-foreground w-14">{item.item_ref ?? ''}</td>
      <td className="px-2 py-1.5 text-sm" style={{ paddingLeft: item.is_heading ? '8px' : '24px' }}>
        {item.is_heading ? <strong>{item.description}</strong> : item.description}
        {item.is_deduction && <span className="ml-2 text-xs text-red-500">(deduct)</span>}
        {item.is_manual_override && <span className="ml-2 text-xs text-orange-500">⚠ manual</span>}
      </td>
      <td className="px-2 py-1.5 text-xs text-center">{item.nos && item.nos !== 1 ? item.nos : ''}</td>
      <td className="px-2 py-1.5 text-xs text-center">{item.length ?? ''}</td>
      <td className="px-2 py-1.5 text-xs text-center">{item.width ?? ''}</td>
      <td className="px-2 py-1.5 text-xs text-center">{item.height ?? ''}</td>
      <td className="px-2 py-1.5 text-xs font-semibold text-right">
        {item.is_heading ? '' : (item.quantity ? (item.is_deduction ? `-${Math.abs(item.quantity)}` : item.quantity.toFixed(3)) : '0.000')}
      </td>
      <td className="px-2 py-1.5 text-xs text-muted-foreground">{item.unit ?? ''}</td>
      <td className="px-2 py-1.5">
        {!item.is_heading && item.formula_display && (
          <span className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">{item.formula_display}</span>
        )}
      </td>
    </tr>
  )
}

export default function MeasurementPage() {
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [activeMB, setActiveMB] = useState<MB|null>(null)
  const [showNewMB, setShowNewMB] = useState(false)
  const [mbTitle, setMBTitle] = useState('Measurement Book')
  const [showAddRow, setShowAddRow] = useState(false)
  const [rowForm, setRowForm] = useState({
    description: '', unit: 'm3', nos: 1, length: 0, width: 0, height: 0,
    item_ref: '', is_heading: false, is_deduction: false,
    is_manual_override: false, quantity: 0,
  })
  const [sort, setSort] = useState(0)

  const { data: projects } = useQuery({
    queryKey: ['projects-list'], queryFn: () => api.get('/projects/?limit=200').then(r => r.data.data)
  })

  const { data: books, refetch: refetchBooks } = useQuery({
    queryKey: ['mb-list', projectId],
    queryFn: () => projectId ? api.get(`/measurements/project/${projectId}`).then(r => r.data) : Promise.resolve([]),
    enabled: !!projectId,
  })

  const { data: mbDetail, refetch: refetchDetail } = useQuery({
    queryKey: ['mb-detail', activeMB?.id],
    queryFn: () => activeMB ? api.get(`/measurements/${activeMB.id}`).then(r => r.data) : Promise.resolve(null),
    enabled: !!activeMB?.id,
  })

  const createMB = useMutation({
    mutationFn: () => api.post('/measurements/', { project_id: projectId, title: mbTitle }),
    onSuccess: (res) => {
      setActiveMB(res.data); refetchBooks()
      setShowNewMB(false); setMBTitle('Measurement Book')
      toast.success('Measurement book created')
    },
  })

  const addRow = useMutation({
    mutationFn: (data: typeof rowForm) => api.post(`/measurements/${activeMB!.id}/items`, {
      ...data, sort_order: sort,
    }),
    onSuccess: () => {
      refetchDetail(); setSort(s => s + 1)
      setRowForm({ description:'', unit:'m3', nos:1, length:0, width:0, height:0, item_ref:'', is_heading:false, is_deduction:false, is_manual_override:false, quantity:0 })
      toast.success('Row added')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Error'),
  })

  const delRow = useMutation({
    mutationFn: (itemId: string) => api.delete(`/measurements/${activeMB!.id}/items/${itemId}`),
    onSuccess: () => { refetchDetail(); toast.success('Row deleted') },
  })

  const items: MBItem[] = mbDetail?.items ?? []
  const totalByUnit: Record<string, number> = {}
  for (const it of items) {
    if (!it.is_heading && it.quantity) {
      const key = `${it.description}|${it.unit ?? ''}`
      totalByUnit[key] = (totalByUnit[key] ?? 0) + it.quantity
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><Ruler className="h-5 w-5"/>Measurement Book</h1>
          <p className="text-sm text-muted-foreground">Dimensional entries with automatic formula display</p>
        </div>
      </div>

      {/* Project + Book Selector */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="space-y-1">
          <Label>Project</Label>
          <Select value={projectId} onValueChange={v => { setProjectId(v); setActiveMB(null) }}>
            <SelectTrigger><SelectValue placeholder="Select project"/></SelectTrigger>
            <SelectContent>{(projects ?? []).map((p: any) => <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        {projectId && (
          <div className="space-y-1">
            <Label>Measurement Book</Label>
            <div className="flex gap-2">
              <Select value={activeMB?.id ?? ''} onValueChange={id => {
                const mb = (books ?? []).find((b: MB) => b.id === id)
                setActiveMB(mb ?? null)
              }}>
                <SelectTrigger className="flex-1"><SelectValue placeholder="Select book"/></SelectTrigger>
                <SelectContent>{(books ?? []).map((b: MB) => <SelectItem key={b.id} value={b.id}>{b.mb_number} — {b.title}</SelectItem>)}</SelectContent>
              </Select>
              <Button size="sm" onClick={() => setShowNewMB(true)}><Plus className="h-4 w-4"/></Button>
            </div>
          </div>
        )}
      </div>

      {/* New MB dialog */}
      {showNewMB && (
        <Card className="border-primary/30">
          <CardContent className="p-4 flex gap-3 items-end">
            <div className="flex-1 space-y-1"><Label>Book Title</Label>
              <Input value={mbTitle} onChange={e => setMBTitle(e.target.value)}/>
            </div>
            <Button onClick={() => createMB.mutate()} disabled={createMB.isPending}>
              {createMB.isPending ? <Loader2 className="h-4 w-4 animate-spin"/> : <Check className="h-4 w-4"/>} Create
            </Button>
            <Button variant="ghost" onClick={() => setShowNewMB(false)}><X className="h-4 w-4"/></Button>
          </CardContent>
        </Card>
      )}

      {/* Measurement Table */}
      {activeMB && (
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base">{mbDetail?.mb_number} — {mbDetail?.title}</CardTitle>
            <Button size="sm" onClick={() => setShowAddRow(!showAddRow)}>
              <Plus className="h-4 w-4 mr-1"/>Add Row
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {/* Add Row Form */}
            {showAddRow && (
              <div className="border-b bg-muted/30 p-3 space-y-3">
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={rowForm.is_heading} onChange={e => setRowForm(f => ({...f, is_heading: e.target.checked}))}/>
                    Section Heading
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={rowForm.is_deduction} onChange={e => setRowForm(f => ({...f, is_deduction: e.target.checked}))}/>
                    Deduction
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={rowForm.is_manual_override} onChange={e => setRowForm(f => ({...f, is_manual_override: e.target.checked}))}/>
                    Manual Override
                  </label>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-6 gap-2 items-end">
                  <div className="col-span-2 md:col-span-1 space-y-1"><Label className="text-xs">Ref</Label>
                    <Input className="h-8 text-xs" placeholder="A.1" value={rowForm.item_ref} onChange={e => setRowForm(f => ({...f, item_ref: e.target.value}))}/>
                  </div>
                  <div className="col-span-2 md:col-span-3 space-y-1"><Label className="text-xs">Description *</Label>
                    <Input className="h-8 text-xs" placeholder="RCC M20 in isolated footings" value={rowForm.description} onChange={e => setRowForm(f => ({...f, description: e.target.value}))}/>
                  </div>
                  <div className="space-y-1"><Label className="text-xs">Unit</Label>
                    <Select value={rowForm.unit} onValueChange={v => setRowForm(f => ({...f, unit: v}))}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue/></SelectTrigger>
                      <SelectContent>{UNITS.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                </div>
                {!rowForm.is_heading && (
                  <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
                    {[['Nos', 'nos', 1], ['Length', 'length', 0], ['Width', 'width', 0], ['Height/Depth', 'height', 0]].map(([label, key, def]) => (
                      <div key={key as string} className={`space-y-1 ${key === 'height' ? 'col-span-2' : ''}`}>
                        <Label className="text-xs">{label as string}</Label>
                        <Input type="number" step="0.001" className="h-8 text-xs"
                          value={(rowForm as any)[key as string] || ''}
                          placeholder={key === 'nos' ? '1' : '0'}
                          onChange={e => setRowForm(f => ({...f, [key as string]: parseFloat(e.target.value) || 0}))}/>
                      </div>
                    ))}
                    {rowForm.is_manual_override && (
                      <div className="col-span-2 space-y-1"><Label className="text-xs">Manual Qty</Label>
                        <Input type="number" step="0.001" className="h-8 text-xs" value={rowForm.quantity}
                          onChange={e => setRowForm(f => ({...f, quantity: parseFloat(e.target.value) || 0}))}/>
                      </div>
                    )}
                  </div>
                )}
                {/* Formula preview */}
                {!rowForm.is_heading && !rowForm.is_manual_override && (
                  <div className="text-xs text-muted-foreground font-mono bg-muted px-3 py-1.5 rounded">
                    <Calculator className="h-3 w-3 inline mr-1"/>
                    {[rowForm.nos !== 1 ? rowForm.nos : null, rowForm.length || null, rowForm.width || null, rowForm.height || null]
                      .filter(Boolean).join(' × ')} = {
                        [rowForm.nos !== 1 ? rowForm.nos : 1, rowForm.length || 1, rowForm.width || 1, rowForm.height || 1]
                          .reduce((a, b) => (a || 1) * (b || 1), undefined as any)
                        // Simple preview calc
                      } {rowForm.unit}
                  </div>
                )}
                <div className="flex gap-2">
                  <Button size="sm" disabled={!rowForm.description || addRow.isPending} onClick={() => addRow.mutate(rowForm)}>
                    {addRow.isPending ? <Loader2 className="h-4 w-4 animate-spin"/> : <Plus className="h-4 w-4"/>} Add
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setShowAddRow(false)}>Cancel</Button>
                </div>
              </div>
            )}

            {/* Measurement table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-primary text-white">
                  <tr>
                    {['Ref','Description','Nos','L','W','H/D','Qty','Unit','Formula'].map(h => (
                      <th key={h} className="px-2 py-2 text-left text-xs font-medium">{h}</th>
                    ))}
                    <th className="px-2 py-2 text-xs"></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => (
                    <tr key={item.id} className={`border-b hover:bg-muted/20 group ${item.is_heading ? 'bg-primary/5 font-semibold' : ''} ${item.is_deduction ? 'text-red-600' : ''}`}>
                      <td className="px-2 py-1.5 text-xs text-muted-foreground">{item.item_ref ?? ''}</td>
                      <td className="px-2 py-1.5 text-sm" style={{paddingLeft: item.is_heading ? '8px' : '20px'}}>
                        {item.is_heading ? <strong>{item.description}</strong> : item.description}
                        {item.is_deduction && <span className="ml-1 text-xs text-red-400">(deduct)</span>}
                        {item.is_manual_override && <span className="ml-1 text-xs text-orange-400">⚠manual</span>}
                      </td>
                      <td className="px-2 py-1.5 text-xs text-center">{!item.is_heading && item.nos !== 1 ? item.nos : ''}</td>
                      <td className="px-2 py-1.5 text-xs text-center">{!item.is_heading ? (item.length ?? '') : ''}</td>
                      <td className="px-2 py-1.5 text-xs text-center">{!item.is_heading ? (item.width ?? '') : ''}</td>
                      <td className="px-2 py-1.5 text-xs text-center">{!item.is_heading ? (item.height ?? '') : ''}</td>
                      <td className="px-2 py-1.5 text-xs font-bold text-right">
                        {!item.is_heading ? (item.quantity != null ? (item.is_deduction ? `-${Math.abs(item.quantity).toFixed(3)}` : item.quantity.toFixed(3)) : '0.000') : ''}
                      </td>
                      <td className="px-2 py-1.5 text-xs">{!item.is_heading ? (item.unit ?? '') : ''}</td>
                      <td className="px-2 py-1.5 max-w-xs">
                        {item.formula_display && <span className="text-xs font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">{item.formula_display}</span>}
                      </td>
                      <td className="px-2 py-1.5 opacity-0 group-hover:opacity-100">
                        <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-destructive" onClick={() => delRow.mutate(item.id)}>
                          <Trash2 className="h-3 w-3"/>
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && (
                    <tr><td colSpan={10} className="text-center py-12 text-muted-foreground text-sm">
                      No measurements yet. Click "Add Row" to start entering dimensions.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Quantity Summary */}
            {Object.keys(totalByUnit).length > 0 && (
              <div className="border-t p-4">
                <p className="text-sm font-semibold mb-2">Quantity Summary</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {Object.entries(totalByUnit).map(([key, qty]) => {
                    const [desc, unit] = key.split('|')
                    return (
                      <div key={key} className="bg-muted/50 rounded p-2">
                        <p className="text-xs text-muted-foreground truncate">{desc}</p>
                        <p className="text-sm font-bold">{qty.toFixed(3)} <span className="text-xs font-normal text-muted-foreground">{unit}</span></p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!activeMB && projectId && (
        <div className="text-center py-16 text-muted-foreground">
          <Ruler className="h-12 w-12 mx-auto mb-3 opacity-20"/>
          <p>Select or create a Measurement Book to start entering dimensions</p>
        </div>
      )}
      {!projectId && (
        <div className="text-center py-16 text-muted-foreground">
          <Ruler className="h-12 w-12 mx-auto mb-3 opacity-20"/>
          <p>Select a project to open its Measurement Books</p>
        </div>
      )}
    </div>
  )
}
