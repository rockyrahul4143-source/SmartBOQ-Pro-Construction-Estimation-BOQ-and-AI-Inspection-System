import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Trash2, Calculator, Download, Upload, FileText,
  ChevronDown, ChevronUp, AlertTriangle, CheckCircle2,
  Loader2, ListChecks, Info,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'
import BBSFilesTab from './BBSFilesTab'
import ManualBeamBBS from '@/components/bbs/ManualBeamBBS'
import ManualColumnBBS from '@/components/bbs/ManualColumnBBS'

// ── helpers ───────────────────────────────────────────
const fmt = (n?: number | null, dec = 0) =>
  n == null ? '—' : n.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec })

const statusBadge = (s: string) => {
  if (s === 'calculated')       return <Badge className="bg-green-600 text-white text-xs">Calculated</Badge>
  if (s === 'verify_required')  return <Badge variant="destructive" className="text-xs">Verify</Badge>
  if (s === 'conflict')         return <Badge variant="destructive" className="text-xs">Conflict</Badge>
  if (s === 'missing_input')    return <Badge className="bg-yellow-500 text-white text-xs">Missing Input</Badge>
  return <Badge variant="outline" className="text-xs">{s}</Badge>
}

const MEMBER_TYPES = ['beam','column','slab','footing']

export default function BBSPage() {
  const qc = useQueryClient()
  const [projectId,  setProjectId]  = useState('')
  const [sheetId,    setSheetId]    = useState('')
  const [tab,        setTab]        = useState<'files'|'manual'|'auto'|'calc'>('files')
  const [showNewSheet, setShowNewSheet] = useState(false)
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [newSheet, setNewSheet] = useState({ title:'', member_type:'beam', fck:25, fy:415, clear_cover:25, notes:'' })
  const [calcReq, setCalcReq] = useState<any>({})
  const [calcResult, setCalcResult] = useState<any>(null)
  const [calcType, setCalcType] = useState('beam-bar')
  const [autoFile, setAutoFile] = useState<File|null>(null)
  const [autoQuery, setAutoQuery] = useState('all')
  const [autoResult, setAutoResult] = useState<any>(null)

  const { data: projects } = useQuery({
    queryKey: ['projects-list'],
    queryFn:  () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data),
  })

  const { data: sheets, refetch: refetchSheets } = useQuery({
    queryKey: ['bbs-sheets', projectId],
    queryFn:  () => api.get(`/bbs/project/${projectId}`).then(r => r.data),
    enabled: !!projectId,
  })

  const { data: sheet } = useQuery({
    queryKey: ['bbs-sheet', sheetId],
    queryFn:  () => api.get(`/bbs/${sheetId}`).then(r => r.data),
    enabled: !!sheetId,
  })

  const { data: summary } = useQuery({
    queryKey: ['bbs-summary', sheetId],
    queryFn:  () => api.get(`/bbs/${sheetId}/summary`).then(r => r.data),
    enabled:  !!sheetId && summaryOpen,
  })

  const createSheet = useMutation({
    mutationFn: () => api.post(`/bbs/project/${projectId}`, newSheet),
    onSuccess: ({ data }) => {
      setSheetId(data.id)
      setShowNewSheet(false)
      refetchSheets()
      qc.invalidateQueries({ queryKey: ['bbs-sheets', projectId] })
      toast.success('BBS sheet created')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to create sheet'),
  })

  const quickCalc = useMutation({
    mutationFn: () => api.post(`/bbs/calc/${calcType}`, calcReq),
    onSuccess: ({ data }) => setCalcResult(data),
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Calculation failed'),
  })

  const autoExtract = useMutation({
    mutationFn: async () => {
      if (!autoFile) throw new Error('No file')
      const fd = new FormData()
      fd.append('file', autoFile)
      fd.append('member_query', autoQuery)
      return api.post(`/bbs/project/${projectId}/extract-drawing`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    onSuccess: ({ data }) => setAutoResult(data),
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Extraction failed'),
  })

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <ListChecks className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-bold">Bar Bending Schedule (BBS)</h2>
        </div>
        <div className="flex gap-2">
          {(['files','manual','auto','calc'] as const).map(t => (
            <Button key={t} size="sm"
              variant={tab === t ? 'default' : 'outline'}
              onClick={() => setTab(t)}>
              {t === 'files' ? '📁 Drawings & Schedules' : t === 'manual' ? 'Manual BBS' : t === 'auto' ? 'Auto from Drawing' : 'Quick Calc'}
            </Button>
          ))}
        </div>
      </div>

      {/* Project selector */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="space-y-1.5 min-w-[240px]">
              <Label>Project *</Label>
              <Select value={projectId} onValueChange={v => { setProjectId(v); setSheetId('') }}>
                <SelectTrigger><SelectValue placeholder="Select project..." /></SelectTrigger>
                <SelectContent>{(projects ?? []).map((p: any) => (
                  <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                ))}</SelectContent>
              </Select>
            </div>
            {projectId && sheets && (
              <div className="space-y-1.5 min-w-[220px]">
                <Label>BBS Sheet</Label>
                <Select value={sheetId} onValueChange={setSheetId}>
                  <SelectTrigger><SelectValue placeholder="Select sheet..." /></SelectTrigger>
                  <SelectContent>
                    {(sheets ?? []).map((s: any) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.sheet_number} — {s.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {projectId && (
              <Button size="sm" variant="outline" onClick={() => setShowNewSheet(s => !s)}>
                <Plus className="h-4 w-4 mr-1" /> New Sheet
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* New Sheet Form */}
      {/* ── DRAWINGS & SCHEDULES TAB ──────────────────── */}
      {tab === 'files' && projectId && <BBSFilesTab projectId={projectId} />}
      {tab === 'files' && !projectId && (
        <Card><CardContent className="py-12 text-center text-muted-foreground text-sm">Select a project first to upload files.</CardContent></Card>
      )}      {showNewSheet && (
        <Card className="border-primary/30">
          <CardHeader className="pb-2"><CardTitle className="text-sm">Create New BBS Sheet</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="col-span-2 space-y-1">
                <Label className="text-xs">Sheet Title *</Label>
                <Input value={newSheet.title} onChange={e => setNewSheet(s=>({...s,title:e.target.value}))} placeholder="e.g. Beam BBS — Ground Floor" className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Member Type</Label>
                <Select value={newSheet.member_type} onValueChange={v=>setNewSheet(s=>({...s,member_type:v}))}>
                  <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                  <SelectContent>{MEMBER_TYPES.map(t=><SelectItem key={t} value={t}>{t.toUpperCase()}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">fck (MPa)</Label>
                <Input type="number" value={newSheet.fck} onChange={e=>setNewSheet(s=>({...s,fck:+e.target.value}))} className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">fy (MPa)</Label>
                <Input type="number" value={newSheet.fy} onChange={e=>setNewSheet(s=>({...s,fy:+e.target.value}))} className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Clear Cover (mm)</Label>
                <Input type="number" value={newSheet.clear_cover} onChange={e=>setNewSheet(s=>({...s,clear_cover:+e.target.value}))} className="h-8" />
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <Button size="sm" onClick={() => createSheet.mutate()} disabled={!newSheet.title || createSheet.isPending}>
                {createSheet.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} Create Sheet
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowNewSheet(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── MANUAL BBS TAB ─────────────────────────────── */}
      {tab === 'manual' && !sheetId && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground text-sm">Please select or create a BBS sheet to start Manual BBS workflow.</p>
          </CardContent>
        </Card>
      )}
      
      {tab === 'manual' && sheetId && sheet && (
        <div className="space-y-4">
          {/* Sheet header info */}
          <Card className="border-primary/30">
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-sm">{sheet.sheet_number}</span>
                  <span className="text-muted-foreground text-sm">—</span>
                  <span className="text-sm">{sheet.title}</span>
                  <Badge variant="outline" className="text-xs">{sheet.member_type.toUpperCase()}</Badge>
                  <Badge variant="outline" className="text-xs">M{sheet.fck} / Fe{sheet.fy}</Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Render member-specific component based on sheet.member_type */}
          {sheet.member_type === 'beam' && (
            <ManualBeamBBS 
              projectId={projectId} 
              sheetId={sheetId} 
              sheet={sheet}
            />
          )}

          {sheet.member_type === 'column' && (
            <ManualColumnBBS 
              projectId={projectId} 
              sheetId={sheetId} 
              sheet={sheet}
            />
          )}

          {!['beam', 'column'].includes(sheet.member_type) && (
            <Card className="border-amber-300 bg-amber-50/30">
              <CardContent className="p-6 text-center">
                <AlertTriangle className="h-8 w-8 text-amber-600 mx-auto mb-2" />
                <p className="font-semibold text-amber-900">Member-Specific BBS Not Available</p>
                <p className="text-sm text-amber-700 mt-1">
                  Manual BBS for <strong>{sheet.member_type.toUpperCase()}</strong> is not yet implemented.
                </p>
                <p className="text-xs text-amber-600 mt-2">
                  Currently supported: BEAM, COLUMN
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ── AUTO BBS FROM DRAWING ─────────────────────── */}
      {tab === 'auto' && (
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2">
            <Upload className="h-5 w-5" /> Auto BBS from Drawing / Schedule
          </CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
              <div className="text-sm text-blue-800">
                <p className="font-semibold mb-1">Supported formats:</p>
                <ul className="list-disc ml-4 space-y-0.5 text-xs">
                  <li><strong>DXF</strong> — AutoCAD DXF files (geometry extraction, dimensions, text)</li>
                  <li><strong>PDF</strong> — Structural drawing PDFs (reference only — enter values in Manual BBS)</li>
                  <li><strong>DWG</strong> — Open in AutoCAD → Save As DXF 2010 ASCII → re-upload</li>
                </ul>
              </div>
            </div>
            {!projectId && <p className="text-sm text-muted-foreground">Select a project first.</p>}
            {projectId && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label>Upload Drawing File</Label>
                    <Input type="file" accept=".dxf,.pdf,.dwg"
                      onChange={e => setAutoFile(e.target.files?.[0] ?? null)} />
                    {autoFile && <p className="text-xs text-muted-foreground">{autoFile.name} ({(autoFile.size/1024).toFixed(1)} KB)</p>}
                  </div>
                  <div className="space-y-1.5">
                    <Label>Member Query (optional)</Label>
                    <Input value={autoQuery} onChange={e => setAutoQuery(e.target.value)}
                      placeholder="all / EB5 / C1 / beam GF" />
                    <p className="text-xs text-muted-foreground">Examples: "all", "EB5", "column C1", "beam ground floor"</p>
                  </div>
                </div>
                <Button onClick={() => autoExtract.mutate()} disabled={!autoFile || autoExtract.isPending}>
                  {autoExtract.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Upload className="h-4 w-4 mr-1" />}
                  Extract from Drawing
                </Button>
              </div>
            )}
            {autoResult && (
              <div className="space-y-3 mt-4">
                <p className="font-semibold text-sm">Extraction Results — {autoResult.filename}</p>
                {(autoResult.extracted ?? []).map((item: any, i: number) => (
                  <Card key={i} className={item.status === 'verify_required' ? 'border-orange-300' : 'border-green-300'}>
                    <CardContent className="p-4">
                      <div className="flex items-start gap-2 mb-2">
                        {item.status === 'verify_required'
                          ? <AlertTriangle className="h-4 w-4 text-orange-500 mt-0.5" />
                          : <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5" />}
                        <span className="font-semibold">{item.member_mark}</span>
                        <Badge variant="outline" className="text-xs">{item.source}</Badge>
                        <Badge variant={item.status === 'verify_required' ? 'destructive' : 'outline'} className="text-xs">{item.status}</Badge>
                      </div>
                      {item.message && <p className="text-sm text-muted-foreground">{item.message}</p>}
                      {item.building_footprint_m2 > 0 && (
                        <div className="grid grid-cols-3 gap-2 text-xs mt-2">
                          <div className="bg-muted/40 p-2 rounded"><p className="text-muted-foreground">Footprint</p><p className="font-bold">{item.building_footprint_m2} m²</p></div>
                          <div className="bg-muted/40 p-2 rounded"><p className="text-muted-foreground">Wall Length</p><p className="font-bold">{item.wall_length_m} m</p></div>
                          <div className="bg-muted/40 p-2 rounded"><p className="text-muted-foreground">Source</p><p className="font-bold">DXF Geometry</p></div>
                        </div>
                      )}
                      {item.warnings?.length > 0 && (
                        <details className="mt-2">
                          <summary className="text-xs text-muted-foreground cursor-pointer">Warnings ({item.warnings.length})</summary>
                          <ul className="mt-1 space-y-1">{item.warnings.map((w: string, j: number) => (
                            <li key={j} className="text-xs text-yellow-700">• {w}</li>
                          ))}</ul>
                        </details>
                      )}
                    </CardContent>
                  </Card>
                ))}
                <div className="p-3 bg-muted/40 rounded-lg border text-sm">
                  <p className="font-semibold mb-1">Next step:</p>
                  <p className="text-muted-foreground">
                    Review the extracted values. Switch to <strong>Manual BBS</strong> tab to create a BBS sheet
                    and enter/verify the values from this extraction. Use the extracted dimensions as your input reference.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── QUICK CALC TAB ────────────────────────────── */}
      {tab === 'calc' && (
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2">
            <Calculator className="h-5 w-5" /> Quick BBS Calculator
          </CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2 flex-wrap">
              {['beam-bar','column-bar','stirrup','development-length'].map(t => (
                <Button key={t} size="sm" variant={calcType===t?'default':'outline'} onClick={()=>{ setCalcType(t); setCalcResult(null) }}>
                  {t.replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}
                </Button>
              ))}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {calcType === 'beam-bar' && (<>
                <div className="space-y-1"><Label className="text-xs">Clear Span (mm)*</Label><Input type="number" onChange={e=>setCalcReq((r:any)=>({...r,clear_span_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Support Near (mm)</Label><Input type="number" defaultValue={230} onChange={e=>setCalcReq((r:any)=>({...r,support_near_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Support Far (mm)</Label><Input type="number" defaultValue={230} onChange={e=>setCalcReq((r:any)=>({...r,support_far_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Dia (mm)</Label><Input type="number" defaultValue={16} onChange={e=>setCalcReq((r:any)=>({...r,dia_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">No. of Bars</Label><Input type="number" defaultValue={2} onChange={e=>setCalcReq((r:any)=>({...r,num_bars:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">fck (MPa)</Label><Input type="number" defaultValue={20} onChange={e=>setCalcReq((r:any)=>({...r,fck:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">fy (MPa)</Label><Input type="number" defaultValue={500} onChange={e=>setCalcReq((r:any)=>({...r,fy:+e.target.value}))} className="h-8" /></div>
              </>)}
              {calcType === 'column-bar' && (<>
                <div className="space-y-1"><Label className="text-xs">Storey Height (mm)*</Label><Input type="number" onChange={e=>setCalcReq((r:any)=>({...r,storey_height_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Dia (mm)</Label><Input type="number" defaultValue={16} onChange={e=>setCalcReq((r:any)=>({...r,dia_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">No. of Bars</Label><Input type="number" defaultValue={4} onChange={e=>setCalcReq((r:any)=>({...r,num_bars:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Lap (mm, 0=auto)</Label><Input type="number" defaultValue={0} onChange={e=>setCalcReq((r:any)=>({...r,lap_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">fck (MPa)</Label><Input type="number" defaultValue={20} onChange={e=>setCalcReq((r:any)=>({...r,fck:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">fy (MPa)</Label><Input type="number" defaultValue={500} onChange={e=>setCalcReq((r:any)=>({...r,fy:+e.target.value}))} className="h-8" /></div>
              </>)}
              {calcType === 'stirrup' && (<>
                <div className="space-y-1"><Label className="text-xs">B (mm)*</Label><Input type="number" onChange={e=>setCalcReq((r:any)=>({...r,b_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">D (mm)*</Label><Input type="number" onChange={e=>setCalcReq((r:any)=>({...r,d_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Dia (mm)</Label><Input type="number" defaultValue={8} onChange={e=>setCalcReq((r:any)=>({...r,dia_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Cover (mm)</Label><Input type="number" defaultValue={25} onChange={e=>setCalcReq((r:any)=>({...r,cover_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Spacing (mm)</Label><Input type="number" defaultValue={150} onChange={e=>setCalcReq((r:any)=>({...r,spacing_mm:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">Zone Length (mm)</Label><Input type="number" onChange={e=>setCalcReq((r:any)=>({...r,zone_length_mm:+e.target.value}))} className="h-8" /></div>
              </>)}
              {calcType === 'development-length' && (<>
                <div className="space-y-1"><Label className="text-xs">Dia (mm)*</Label><Input type="number" onChange={e=>setCalcReq((r:any)=>({...r,dia:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">fck (MPa)</Label><Input type="number" defaultValue={20} onChange={e=>setCalcReq((r:any)=>({...r,fck:+e.target.value}))} className="h-8" /></div>
                <div className="space-y-1"><Label className="text-xs">fy (MPa)</Label><Input type="number" defaultValue={500} onChange={e=>setCalcReq((r:any)=>({...r,fy:+e.target.value}))} className="h-8" /></div>
              </>)}
            </div>

            <Button onClick={() => {
              if (calcType === 'development-length') {
                const p = new URLSearchParams(calcReq).toString()
                api.get(`/bbs/calc/development-length?${p}`).then(r => setCalcResult(r.data)).catch(e => toast.error(e.response?.data?.detail ?? 'Error'))
              } else {
                quickCalc.mutate()
              }
            }} disabled={quickCalc.isPending}>
              {quickCalc.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Calculator className="h-4 w-4 mr-1" />}
              Calculate
            </Button>

            {calcResult && (
              <Card className="border-green-300 bg-green-50">
                <CardContent className="p-4">
                  <p className="font-semibold text-green-800 mb-3 flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" /> Calculation Result
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {calcResult.cutting_length_mm != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">Cutting Length</p><p className="font-bold">{calcResult.cutting_length_mm} mm</p></div>
                    )}
                    {calcResult.lap_length_mm != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">Lap Length</p><p className="font-bold">{calcResult.lap_length_mm} mm</p></div>
                    )}
                    {calcResult.total_length_mm != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">Total Length</p><p className="font-bold">{calcResult.total_length_mm} mm</p></div>
                    )}
                    {calcResult.total_weight_kg != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">Total Weight</p><p className="font-bold">{calcResult.total_weight_kg} kg</p></div>
                    )}
                    {calcResult.unit_weight_kg_per_m != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">Unit Weight</p><p className="font-bold">{calcResult.unit_weight_kg_per_m} kg/m</p></div>
                    )}
                    {calcResult.development_length_mm != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">Dev Length (Ld)</p><p className="font-bold">{calcResult.development_length_mm} mm</p></div>
                    )}
                    {calcResult.num_stirrups != null && (
                      <div className="bg-white rounded p-2 border"><p className="text-xs text-muted-foreground">No. of Stirrups</p><p className="font-bold">{calcResult.num_stirrups}</p></div>
                    )}
                  </div>
                  {calcResult.formula && (
                    <div className="mt-3 p-2 bg-white rounded border font-mono text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">Formula: </span>{calcResult.formula}
                    </div>
                  )}
                  {calcResult.formula && (
                    <p className="text-xs text-muted-foreground mt-1">Standard: IS 2502, IS 456-2000, SP-34</p>
                  )}
                </CardContent>
              </Card>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
