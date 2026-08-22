/**
 * Drawing Takeoff Page
 * ====================
 * PRINCIPLE: Drawing Vision reads → Formula Engine calculates → Engineer approves
 *
 * Workflow:
 *   1. Upload DXF → analyze → see detected elements
 *   2. Engineer reviews each element (accept / edit / reject)
 *   3. Send verified elements to Measurement Book
 *   4. Quantities computed by formula engine
 *   5. Link to BOQ
 */
import { useState, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Upload, FileText, AlertTriangle, CheckCircle2, XCircle,
  Loader2, Info, Calculator, ChevronDown, ChevronRight,
  ArrowRight, Edit2, Check, X, BookOpen,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

// ── Types ──────────────────────────────────────────────────────────────
interface Dim { value: number | null; unit: string; source: string; confidence: string; raw_text?: string }
interface DetectedElement {
  mark: string; element_type: string; description: string
  length: Dim|null; width: Dim|null; height: Dim|null; depth: Dim|null; nos: Dim|null
  confidence: string; status: string; conflict_notes: string; source_info: string
  formula: string; unit: string; category: string; engineer_action: string
}

const CONFIDENCE_COLORS: Record<string,string> = {
  high:   'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low:    'bg-red-100 text-red-800',
}
const STATUS_ICONS: Record<string, any> = {
  detected:              CheckCircle2,
  engineer_input_required: AlertTriangle,
  conflict_detected:     AlertTriangle,
  not_found:             XCircle,
}
const ELEMENT_TYPE_COLORS: Record<string,string> = {
  column: 'bg-blue-50 border-blue-200',
  beam:   'bg-purple-50 border-purple-200',
  slab:   'bg-green-50 border-green-200',
  footing:'bg-orange-50 border-orange-200',
  wall:   'bg-red-50 border-red-200',
  door:   'bg-teal-50 border-teal-200',
  window: 'bg-cyan-50 border-cyan-200',
}

// ── Dimension editor inline ────────────────────────────────────────────
function DimCell({ dim, label, onChange }: { dim: Dim|null; label: string; onChange: (v: number|null)=>void }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(String(dim?.value ?? ''))

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <Input autoFocus type="number" step="0.001" className="h-6 w-20 text-xs"
          value={val} onChange={e=>setVal(e.target.value)}
          onBlur={() => { onChange(parseFloat(val)||null); setEditing(false) }}
          onKeyDown={e => { if(e.key==='Enter'){onChange(parseFloat(val)||null);setEditing(false)} if(e.key==='Escape') setEditing(false) }}
        />
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1 cursor-pointer group" onClick={()=>setEditing(true)}>
      <span className="text-xs font-medium">{label}:</span>
      {dim?.value != null ? (
        <span className={`text-xs px-1 rounded ${CONFIDENCE_COLORS[dim.confidence] ?? ''}`}>{dim.value}</span>
      ) : (
        <span className="text-xs text-red-500 italic">required</span>
      )}
      <Edit2 className="h-2.5 w-2.5 opacity-0 group-hover:opacity-70 text-muted-foreground"/>
    </div>
  )
}

// ── Element card ───────────────────────────────────────────────────────
function ElementCard({
  element, approved, rejected,
  onApprove, onReject, onEdit,
}: {
  element: DetectedElement
  approved: boolean; rejected: boolean
  onApprove: ()=>void; onReject: ()=>void
  onEdit: (key: string, val: number|null)=>void
}) {
  const [expanded, setExpanded] = useState(false)
  const StatusIcon = STATUS_ICONS[element.status] ?? Info
  const borderCls = approved ? 'border-green-400 bg-green-50' : rejected ? 'border-red-300 bg-red-50 opacity-60' : (ELEMENT_TYPE_COLORS[element.element_type] ?? 'bg-white border-border')

  return (
    <div className={`border rounded-lg overflow-hidden ${borderCls}`}>
      <div className="flex items-center justify-between p-3 cursor-pointer" onClick={()=>setExpanded(e=>!e)}>
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
          <span className="font-mono font-bold text-sm bg-white/70 px-1.5 rounded">{element.mark}</span>
          <span className="text-sm">{element.description}</span>
          <Badge variant="outline" className="text-xs capitalize">{element.element_type}</Badge>
          <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${CONFIDENCE_COLORS[element.confidence]??''}`}>
            {element.confidence}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground mr-2">{element.unit}</span>
          {!approved && !rejected && (
            <>
              <Button size="sm" variant="ghost" className="h-6 px-2 text-xs text-green-700 hover:bg-green-100" onClick={e=>{e.stopPropagation();onApprove()}}>
                <Check className="h-3 w-3 mr-1"/>Accept
              </Button>
              <Button size="sm" variant="ghost" className="h-6 px-2 text-xs text-red-600 hover:bg-red-100" onClick={e=>{e.stopPropagation();onReject()}}>
                <X className="h-3 w-3 mr-1"/>Reject
              </Button>
            </>
          )}
          {approved && <span className="text-xs text-green-700 font-semibold flex items-center gap-1"><CheckCircle2 className="h-3 w-3"/>Accepted</span>}
          {rejected && <span className="text-xs text-red-600 font-semibold flex items-center gap-1"><XCircle className="h-3 w-3"/>Rejected</span>}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t bg-white/60">
          {/* Status & source */}
          <div className="flex gap-2 flex-wrap pt-2">
            <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1
              ${element.status === 'detected' ? 'bg-green-100 text-green-700' :
                element.status === 'engineer_input_required' ? 'bg-orange-100 text-orange-700' :
                'bg-red-100 text-red-700'}`}>
              <StatusIcon className="h-3 w-3"/>
              {element.status.replace(/_/g,' ')}
            </span>
            {element.source_info && <span className="text-xs text-muted-foreground">Source: {element.source_info}</span>}
          </div>

          {/* Conflict notes */}
          {element.conflict_notes && (
            <div className="text-xs bg-orange-50 border border-orange-200 rounded p-2 text-orange-800">
              <AlertTriangle className="h-3 w-3 inline mr-1"/>
              {element.conflict_notes}
            </div>
          )}

          {/* Dimension editors */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              ['length',  'L (m)'],
              ['width',   'B/W (m)'],
              ['height',  'D/H (m)'],
              ['depth',   'Depth (m)'],
              ['nos',     'Nos'],
            ].map(([key, label]) => (
              <div key={key} className="space-y-1">
                <Label className="text-xs text-muted-foreground">{label}</Label>
                <DimCell
                  dim={(element as any)[key]}
                  label=""
                  onChange={v => onEdit(key, v)}
                />
              </div>
            ))}
          </div>

          {/* Formula display */}
          {element.formula && (
            <div className="text-xs font-mono bg-muted/50 px-3 py-1.5 rounded flex items-center gap-2">
              <Calculator className="h-3 w-3 text-primary shrink-0"/>
              <span className="text-muted-foreground">Formula:</span>
              <span className="text-primary font-semibold">{element.formula}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────
export default function DrawingTakeoffPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [projectId, setProjectId] = useState('')
  const [units, setUnits] = useState('mm')
  const [file, setFile] = useState<File|null>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [elements, setElements] = useState<DetectedElement[]>([])
  const [approved, setApproved] = useState<Set<string>>(new Set())
  const [rejected, setRejected] = useState<Set<string>>(new Set())
  const [storeyH, setStoreyH] = useState('3.0')
  const [mbTitle, setMbTitle] = useState('Drawing Takeoff')
  const [mbResult, setMbResult] = useState<any>(null)
  const [filterType, setFilterType] = useState('all')

  const { data: projects } = useQuery({ queryKey:['projects-list'], queryFn:()=>api.get('/projects/?limit=200').then(r=>r.data.data) })
  const { data: guide } = useQuery({ queryKey:['formula-guide'], queryFn:()=>api.get('/drawing-takeoff/formula-guide').then(r=>r.data) })

  const analyzeMut = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('No file')
      const fd = new FormData()
      fd.append('file', file)
      fd.append('units', units)
      return api.post('/drawing-takeoff/analyze', fd, { headers:{'Content-Type':'multipart/form-data'} })
    },
    onSuccess: ({ data }) => {
      setAnalysis(data)
      setElements(data.analysis.elements ?? [])
      setApproved(new Set(
        (data.analysis.elements ?? [])
          .filter((e: DetectedElement) => e.engineer_action === 'suggested_accept')
          .map((e: DetectedElement) => e.mark)
      ))
      setRejected(new Set())
      setMbResult(null)
      toast.success(`Detected ${data.analysis.total_elements} elements`)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Analysis failed'),
  })

  const sendMut = useMutation({
    mutationFn: () => {
      const verifiedElements = elements
        .filter(e => approved.has(e.mark) && !rejected.has(e.mark))
        .map(e => e)
      if (!verifiedElements.length) throw new Error('No accepted elements')
      return api.post('/drawing-takeoff/send-to-mb', {
        project_id: projectId,
        mb_title: mbTitle,
        storey_height_m: parseFloat(storeyH) || 3.0,
        verified_elements: verifiedElements,
      })
    },
    onSuccess: ({ data }) => { setMbResult(data); toast.success(`Measurement Book ${data.mb_number} created with ${data.items_created} items`) },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Error sending to MB'),
  })

  const editElement = (mark: string, key: string, val: number|null) => {
    setElements(prev => prev.map(e => {
      if (e.mark !== mark) return e
      const updated = { ...e }
      if ((updated as any)[key] && typeof (updated as any)[key] === 'object') {
        (updated as any)[key] = { ...(updated as any)[key], value: val, source: 'user_input' }
      } else {
        (updated as any)[key] = { value: val, unit: 'm', source: 'user_input', confidence: 'high' }
      }
      return updated
    }))
  }

  const acceptAll = () => setApproved(new Set(elements.map(e => e.mark)))
  const filteredElements = filterType === 'all' ? elements : elements.filter(e => e.element_type === filterType)
  const elementTypes = [...new Set(elements.map(e => e.element_type))]
  const acceptedCount = elements.filter(e => approved.has(e.mark) && !rejected.has(e.mark)).length
  const needsInput = elements.filter(e => e.status === 'engineer_input_required').length

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold flex items-center gap-2">
          <FileText className="h-5 w-5"/>Drawing Takeoff
        </h1>
        <p className="text-sm text-muted-foreground">
          DXF → Element Detection → Engineer Verification → Measurement Book → BOQ
        </p>
      </div>

      {/* Principle banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-start gap-2 text-xs text-blue-800">
        <Info className="h-4 w-4 shrink-0 mt-0.5"/>
        <div>
          <strong>How this works:</strong> Drawing analysis extracts element labels and schedule dimensions (C1 = 300×300 etc.).
          It does NOT calculate quantities. After you verify each element's dimensions,
          the existing formula engine computes quantities deterministically.
          <strong> No value enters the system without engineer approval.</strong>
        </div>
      </div>

      {/* Step 1: Upload */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <span className="bg-primary text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold">1</span>
            Upload DXF Drawing
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
            <div className="col-span-2 space-y-1">
              <Label>Project *</Label>
              <Select value={projectId} onValueChange={setProjectId}>
                <SelectTrigger><SelectValue placeholder="Select project"/></SelectTrigger>
                <SelectContent>{(projects??[]).map((p:any)=><SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Drawing Units</Label>
              <Select value={units} onValueChange={setUnits}>
                <SelectTrigger><SelectValue/></SelectTrigger>
                <SelectContent>{['mm','cm','m','ft','in'].map(u=><SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Storey Height (m)</Label>
              <Input type="number" step="0.1" value={storeyH} onChange={e=>setStoreyH(e.target.value)} placeholder="3.0"/>
            </div>
          </div>

          <div className="border-2 border-dashed border-muted-foreground/30 rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
            onClick={()=>fileRef.current?.click()}>
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileText className="h-8 w-8 text-primary"/>
                <div className="text-left">
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">{(file.size/1024).toFixed(1)} KB</p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground/50"/>
                <p className="text-sm font-medium">Click to select DXF file</p>
                <p className="text-xs text-muted-foreground mt-1">AutoCAD DXF only · Structural/architectural plan</p>
              </>
            )}
            <input ref={fileRef} type="file" accept=".dxf" className="hidden" onChange={e=>setFile(e.target.files?.[0]??null)}/>
          </div>

          <Button className="w-full" disabled={!file||!projectId||analyzeMut.isPending} onClick={()=>analyzeMut.mutate()}>
            {analyzeMut.isPending ? <><Loader2 className="h-4 w-4 animate-spin mr-1"/>Analyzing drawing…</> : <><Upload className="h-4 w-4 mr-1"/>Analyze Drawing</>}
          </Button>
        </CardContent>
      </Card>

      {/* Step 2: Drawing Info */}
      {analysis && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className="bg-primary text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold">2</span>
              Drawing Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              {[
                ['Drawing Type', analysis.analysis.drawing_info.drawing_type],
                ['Floor/Level', analysis.analysis.drawing_info.floor_level],
                ['Scale', analysis.analysis.drawing_info.scale],
                ['Units', analysis.units_used],
              ].map(([l,v])=>(
                <div key={l} className="bg-muted/40 rounded p-2">
                  <p className="text-xs text-muted-foreground">{l}</p>
                  <p className="text-xs font-medium">{v || '—'}</p>
                </div>
              ))}
            </div>

            {/* Warnings */}
            {(analysis.analysis.warnings??[]).length > 0 && (
              <div className="space-y-1">
                {analysis.analysis.warnings.map((w:string,i:number)=>(
                  <div key={i} className="text-xs bg-yellow-50 border border-yellow-200 rounded px-3 py-2 text-yellow-800 flex gap-2">
                    <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5"/>{w}
                  </div>
                ))}
              </div>
            )}

            {/* Missing info */}
            {(analysis.analysis.missing_info??[]).length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="text-xs font-semibold text-red-600">Engineer Input Required:</p>
                {analysis.analysis.missing_info.map((m:string,i:number)=>(
                  <div key={i} className="text-xs bg-red-50 border border-red-200 rounded px-3 py-2 text-red-700">{m}</div>
                ))}
              </div>
            )}

            {/* Validation checks */}
            {(analysis.analysis.validation_checks??[]).length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="text-xs font-semibold text-muted-foreground">Validation Checks:</p>
                {analysis.analysis.validation_checks.map((c:any,i:number)=>(
                  <div key={i} className={`text-xs rounded px-3 py-2 border flex gap-2 ${
                    c.status==='OK'?'bg-green-50 border-green-200 text-green-700':
                    c.status==='WARNING'?'bg-orange-50 border-orange-200 text-orange-700':
                    'bg-blue-50 border-blue-200 text-blue-700'}`}>
                    {c.message}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 3: Verify Elements */}
      {elements.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <span className="bg-primary text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold">3</span>
                Verify Detected Elements
              </CardTitle>
              <div className="flex gap-2 items-center flex-wrap">
                <span className="text-xs text-muted-foreground">{acceptedCount}/{elements.length} accepted</span>
                {needsInput > 0 && <span className="text-xs text-orange-600">{needsInput} need input</span>}
                <Button size="sm" variant="outline" onClick={acceptAll} className="h-7 text-xs">Accept All Detected</Button>
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="h-7 w-32 text-xs"><SelectValue/></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    {elementTypes.map(t=><SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Click each element to expand and edit dimensions.
              Elements marked <span className="text-orange-600 font-medium">engineer_input_required</span> need your input before accepting.
            </p>
            {filteredElements.map(el=>(
              <ElementCard
                key={el.mark}
                element={el}
                approved={approved.has(el.mark)}
                rejected={rejected.has(el.mark)}
                onApprove={()=>{ setApproved(s=>{const n=new Set(s);n.add(el.mark);return n}); setRejected(s=>{const n=new Set(s);n.delete(el.mark);return n}) }}
                onReject={()=>{ setRejected(s=>{const n=new Set(s);n.add(el.mark);return n}); setApproved(s=>{const n=new Set(s);n.delete(el.mark);return n}) }}
                onEdit={(key,val)=>editElement(el.mark,key,val)}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Step 4: Send to MB */}
      {acceptedCount > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <span className="bg-primary text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold">4</span>
              Send to Measurement Book
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="bg-green-50 border border-green-200 rounded p-3 text-sm text-green-800">
              <CheckCircle2 className="h-4 w-4 inline mr-2"/>
              <strong>{acceptedCount} elements accepted</strong> — ready to generate quantities using civil engineering formulas.
              Rejected: {rejected.size}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Measurement Book Title</Label>
                <Input value={mbTitle} onChange={e=>setMbTitle(e.target.value)}/>
              </div>
              <div className="space-y-1">
                <Label>Default Storey Height (m)</Label>
                <Input type="number" step="0.1" value={storeyH} onChange={e=>setStoreyH(e.target.value)}/>
              </div>
            </div>
            <Button className="w-full" disabled={sendMut.isPending} onClick={()=>sendMut.mutate()}>
              {sendMut.isPending ? <><Loader2 className="h-4 w-4 animate-spin mr-1"/>Creating…</> :
                <><ArrowRight className="h-4 w-4 mr-1"/>Send {acceptedCount} Elements to Measurement Book</>}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 5: Result */}
      {mbResult && (
        <Card className="border-green-400 bg-green-50">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-6 w-6 text-green-600 shrink-0"/>
              <div>
                <p className="font-semibold text-green-800">Measurement Book Created!</p>
                <p className="text-sm text-green-700 mt-1">
                  <strong>{mbResult.mb_number}</strong> — {mbResult.items_created} items with calculated quantities.
                </p>
                <div className="mt-3 space-y-1 max-h-48 overflow-y-auto">
                  {(mbResult.items??[]).filter((i:any)=>!i.is_heading && i.quantity).map((item:any,i:number)=>(
                    <div key={i} className="bg-white rounded px-3 py-1.5 text-xs flex justify-between">
                      <span>{item.description}</span>
                      <div className="flex gap-3">
                        <span className="font-semibold text-green-700">{item.quantity?.toFixed(3)} {item.unit}</span>
                        {item.formula && <span className="font-mono text-muted-foreground">{item.formula}</span>}
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
                  <BookOpen className="h-3 w-3"/>
                  {mbResult.next_step}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Formula Guide */}
      {guide && !analysis && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Calculator className="h-4 w-4"/>Engineering Formula Reference</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(guide.formulas ?? {}).map(([key, info]: any)=>(
                <div key={key} className="bg-muted/30 rounded p-3">
                  <p className="text-xs font-semibold text-primary capitalize">{key.replace(/_/g,' ')}</p>
                  <p className="text-xs font-mono mt-1 text-blue-700">{info.formula}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{info.example}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-3 italic">{guide.note}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
