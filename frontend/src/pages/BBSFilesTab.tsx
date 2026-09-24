/**
 * BBS Drawings & Schedules Tab — Complete Professional Workflow
 * Upload multiple files → Extract → Cross-file query → NL request → Generate BBS
 */
import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Upload, Trash2, Search, FileText, CheckCircle2, AlertTriangle,
  Loader2, FolderOpen, Info, ArrowRight, Zap, BarChart2, RefreshCw,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/useToast'

const FILE_CATEGORIES = [
  'auto','beam_schedule','column_schedule','slab_schedule','foundation_schedule',
  'structural_plan','structural_plan_cad','reinforcement_detail',
  'section_elevation','general_notes','staircase','other',
]

const STATUS_COLORS: Record<string, string> = {
  complete:      'bg-green-600 text-white',
  partial:       'bg-yellow-500 text-white',
  not_supported: 'bg-slate-400 text-white',
  ocr_required:  'bg-orange-500 text-white',
  failed:        'bg-red-600 text-white',
  pending:       'bg-blue-400 text-white',
}

function FileBadge({ status }: { status: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[status] ?? 'bg-gray-200'}`}>
    {status.replace(/_/g,' ')}
  </span>
}

function FieldRow({ name, r }: { name: string; r: any }) {
  if (!r) return null
  const isFound    = r.status === 'found'
  const isConflict = r.status?.startsWith('CONFLICT')
  const isMissing  = r.status?.startsWith('NOT_FOUND')
  return (
    <div className="flex items-start justify-between gap-2 py-1 border-b last:border-0 text-xs">
      <span className="text-muted-foreground w-36 shrink-0">{name.replace(/_/g,' ')}</span>
      <div className="text-right flex-1">
        {isFound && <span className="font-mono">{typeof r.value==='object' ? JSON.stringify(r.value) : String(r.value ?? '—')}</span>}
        {isConflict && <span className="text-red-600 font-semibold">⚠ CONFLICT — verify drawing</span>}
        {isMissing && <span className="text-orange-500">NOT FOUND</span>}
        {isFound && <div className="text-muted-foreground text-xs">✓ {r.source} — {r.file}</div>}
        {isConflict && r.sources?.map((s:any,i:number)=>(
          <div key={i} className="text-xs text-red-600">{s.source}: {JSON.stringify(s.value)}</div>
        ))}
      </div>
    </div>
  )
}

export default function BBSFilesTab({ projectId, onSheetCreated }: {
  projectId: string; onSheetCreated?: (sheetId: string) => void
}) {
  const qc     = useQueryClient()
  const fRef   = useRef<HTMLInputElement>(null)
  const [files,      setFiles]      = useState<File[]>([])
  const [category,   setCategory]   = useState('auto')
  const [nlInput,    setNlInput]    = useState('')
  const [memberType, setMemberType] = useState('beam')
  const [nlResult,   setNlResult]   = useState<any>(null)
  const [qResult,    setQResult]    = useState<any>(null)
  const [queryStr,   setQueryStr]   = useState('')
  const [genResult,  setGenResult]  = useState<any>(null)
  const [completeMT, setCompleteMT] = useState('all')

  const { data: index, refetch } = useQuery({
    queryKey: ['pf', projectId],
    queryFn:  () => api.get(`/project-files/project/${projectId}`).then(r=>r.data),
    enabled:  !!projectId,
  })

  // Upload (one or many files)
  const uploadMut = useMutation({
    mutationFn: async () => {
      const results = []
      for (const f of files) {
        const fd = new FormData()
        fd.append('file', f)
        fd.append('file_category', category)
        const r = await api.post(`/project-files/project/${projectId}/upload`, fd, {
          headers:{'Content-Type':'multipart/form-data'}
        })
        results.push(r.data)
      }
      return results
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['pf', projectId] })
      setFiles([])
      const total = res.reduce((s:number,r:any)=>s+(r.member_count||0),0)
      toast.success(`${res.length} file(s) uploaded — ${total} members extracted`)
    },
    onError: (e:any) => toast.error(e.response?.data?.detail ?? 'Upload failed'),
  })

  const deleteMut = useMutation({
    mutationFn: (id:string) => api.delete(`/project-files/${id}`),
    onSuccess:  () => { qc.invalidateQueries({queryKey:['pf',projectId]}); toast.success('File removed') },
  })

  const queryMut = useMutation({
    mutationFn: () => api.get(`/project-files/project/${projectId}/query/${encodeURIComponent(queryStr)}`, {params:{member_type:memberType}}),
    onSuccess: ({data}) => setQResult(data),
    onError: (e:any) => toast.error(e.response?.data?.detail ?? 'Query failed'),
  })

  const nlMut = useMutation({
    mutationFn: () => { const fd=new FormData(); fd.append('user_input',nlInput); return api.post(`/project-files/project/${projectId}/nl-request`,fd,{headers:{'Content-Type':'multipart/form-data'}}) },
    onSuccess: ({data}) => {
      setNlResult(data)
      if (data.sheet_id && onSheetCreated) onSheetCreated(data.sheet_id)
      if (data.sheet_id) toast.success(`BBS sheet created — ${data.total_weight_kg} kg`)
    },
    onError: (e:any) => toast.error(e.response?.data?.detail ?? 'Failed'),
  })

  const completeMut = useMutation({
    mutationFn: () => { const fd=new FormData(); fd.append('member_type',completeMT); return api.post(`/project-files/project/${projectId}/generate-complete-bbs`,fd,{headers:{'Content-Type':'multipart/form-data'}}) },
    onSuccess: ({data}) => {
      setGenResult(data)
      if (data.sheet_id && onSheetCreated) onSheetCreated(data.sheet_id)
      toast.success(`Complete BBS — ${data.members_count} members, ${data.total_weight_kg} kg`)
    },
    onError: (e:any) => toast.error(e.response?.data?.detail ?? 'Failed'),
  })

  const allMembers = [...(index?.beams||[]), ...(index?.columns||[])]

  return (
    <div className="space-y-5">
      {/* Info */}
      <div className="flex gap-2 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
        <Info className="h-4 w-4 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">Upload multiple project files. All files are searched together for every BBS request.</p>
          <p className="text-xs mt-0.5">DXF: full geometry. PDF: text-layer schedule extraction (OCR for scanned if pytesseract installed). DWG: convert to DXF first. Excel/CSV: table extraction.</p>
        </div>
      </div>

      {/* Upload */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Upload className="h-4 w-4" /> Add Project Files</CardTitle></CardHeader>
        <CardContent>
          <div className="grid sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <div className="border-2 border-dashed rounded-lg p-4 cursor-pointer hover:border-primary/50 text-center" onClick={()=>fRef.current?.click()}>
                {files.length
                  ? <div className="space-y-1">{files.map((f,i)=><p key={i} className="text-xs">{f.name} ({(f.size/1024).toFixed(1)}KB)</p>)}</div>
                  : <><FolderOpen className="h-6 w-6 mx-auto text-muted-foreground/40 mb-1"/><p className="text-xs text-muted-foreground">Click to select files (multiple allowed)</p><p className="text-xs text-muted-foreground mt-0.5">DXF · PDF · PNG · JPG · DWG · XLSX · CSV</p></>
                }
                <input ref={fRef} type="file" multiple
                  accept=".dxf,.dwg,.pdf,.png,.jpg,.jpeg,.bmp,.xlsx,.xls,.csv"
                  className="hidden" onChange={e=>setFiles(Array.from(e.target.files||[]))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-xs">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="h-8 text-sm"><SelectValue/></SelectTrigger>
                <SelectContent>{FILE_CATEGORIES.map(c=><SelectItem key={c} value={c}>{c.replace(/_/g,' ')}</SelectItem>)}</SelectContent>
              </Select>
              <Button className="w-full" size="sm" onClick={()=>uploadMut.mutate()} disabled={!files.length||uploadMut.isPending}>
                {uploadMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1"/> : <Upload className="h-4 w-4 mr-1"/>}
                Upload & Extract
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* File list */}
      {!!index?.files?.length && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center justify-between">
              <span>Project Files ({index.files.length}) — {allMembers.length} members found</span>
              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={()=>refetch()}>
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {index.files.map((f:any)=>(
              <div key={f.id} className="flex items-center gap-2 p-2 border rounded hover:bg-muted/30">
                <FileText className="h-4 w-4 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{f.original_name}</p>
                  <div className="flex gap-2 text-xs text-muted-foreground flex-wrap">
                    <span>{f.file_type?.toUpperCase()}</span>
                    {f.file_category && <span>· {f.file_category.replace(/_/g,' ')}</span>}
                    {f.file_size_kb && <span>· {f.file_size_kb}KB</span>}
                    {f.member_count>0 && <span className="text-green-700">· {f.member_count} members</span>}
                  </div>
                  {f.extraction_notes && <p className="text-xs text-yellow-700 truncate">{f.extraction_notes.split('\n')[0]}</p>}
                  {f.capability_notes && <p className="text-xs text-blue-600 truncate">{f.capability_notes}</p>}
                </div>
                <FileBadge status={f.extraction_status} />
                <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive shrink-0" onClick={()=>deleteMut.mutate(f.id)}>
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}

            {/* Member index */}
            {allMembers.length > 0 && (
              <div className="mt-3 pt-3 border-t">
                <p className="text-xs font-semibold text-muted-foreground mb-2">MEMBERS ACROSS ALL FILES — click to query:</p>
                <div className="flex flex-wrap gap-1.5">
                  {index.beams?.map((m:string)=>(
                    <button key={m} onClick={()=>{setQueryStr(m);setMemberType('beam')}}
                      className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded hover:bg-blue-200 font-mono">{m}</button>
                  ))}
                  {index.columns?.map((m:string)=>(
                    <button key={m} onClick={()=>{setQueryStr(m);setMemberType('column')}}
                      className="text-xs px-2 py-0.5 bg-purple-100 text-purple-800 rounded hover:bg-purple-200 font-mono">{m}</button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Natural-language request */}
      <Card className="border-primary/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="h-4 w-4 text-amber-500" /> What would you like to calculate?
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Type any civil engineering BBS request. The system searches all uploaded files automatically.
          </p>
          <div className="flex gap-2">
            <Input
              value={nlInput} onChange={e=>setNlInput(e.target.value)}
              placeholder="e.g. Calculate complete BBS of EB5 / Find clear span of all beams / Calculate all column ties"
              className="flex-1"
              onKeyDown={e=>e.key==='Enter'&&nlInput&&nlMut.mutate()}
            />
            <Button onClick={()=>nlMut.mutate()} disabled={!nlInput||nlMut.isPending||!index?.files?.length}>
              {nlMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1"/> : <ArrowRight className="h-4 w-4 mr-1"/>}
              Calculate
            </Button>
          </div>
          {/* Quick request buttons */}
          <div className="flex flex-wrap gap-1.5">
            {[
              "Calculate complete BBS of all beams",
              "Calculate complete BBS for all columns",
              "Calculate all beam stirrups",
              "Calculate all column ties",
              "Find clear span of all beams",
              "Give total steel by diameter",
            ].map(t=>(
              <button key={t} onClick={()=>{setNlInput(t);}} className="text-xs px-2 py-1 bg-muted rounded hover:bg-muted/80 border">{t}</button>
            ))}
          </div>

          {nlResult && (
            <div className="mt-2 space-y-3">
              <div className="p-2 bg-blue-50 rounded text-xs text-blue-800">
                <span className="font-semibold">Interpreted as: </span>{nlResult.parsed_request}
              </div>
              {nlResult.sheet_id && (
                <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded text-sm text-green-800">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-semibold">BBS Sheet created — {nlResult.total_weight_kg} kg total</p>
                    <p className="text-xs">Members: {nlResult.members_processed?.join(', ')} | Files: {nlResult.files_searched?.join(', ')}</p>
                    {nlResult.flags?.length > 0 && (
                      <p className="text-xs text-orange-700 mt-1">⚠ {nlResult.flags.length} field(s) need verification</p>
                    )}
                    <p className="text-xs mt-1">→ View/edit in Manual BBS tab → export Excel/PDF</p>
                  </div>
                </div>
              )}
              {/* Extraction review */}
              {nlResult.extraction_review?.length > 0 && (
                <details>
                  <summary className="text-xs font-semibold cursor-pointer text-primary">
                    Extraction Review ({nlResult.extraction_review.length} members)
                  </summary>
                  <div className="mt-2 space-y-2">
                    {nlResult.extraction_review.map((m:any,i:number)=>(
                      <Card key={i} className="border-slate-200">
                        <CardHeader className="pb-1 pt-2">
                          <p className="text-xs font-semibold font-mono">{m.mark} <Badge variant="outline" className="text-xs ml-1">{m.type}</Badge></p>
                        </CardHeader>
                        <CardContent className="pt-0 pb-2">
                          <div className="grid sm:grid-cols-2 gap-x-4">
                            {Object.entries(m.fields||{}).slice(0,12).map(([k,v]:any)=><FieldRow key={k} name={k} r={v}/>)}
                          </div>
                          {m.flags?.length>0 && (
                            <p className="text-xs text-orange-600 mt-1">
                              Missing: {m.flags.map((f:any)=>f.field).join(', ')}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Complete project BBS */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart2 className="h-4 w-4" /> Generate Complete Project BBS
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 flex-wrap items-center">
            <div className="flex gap-1.5 flex-wrap">
              {['all','beam','column','slab','footing'].map(t=>(
                <Button key={t} size="sm" variant={completeMT===t?'default':'outline'}
                  onClick={()=>setCompleteMT(t)} className="h-7 text-xs">
                  {t.toUpperCase()}
                </Button>
              ))}
            </div>
            <Button size="sm" onClick={()=>completeMut.mutate()} disabled={completeMut.isPending||!index?.files?.length} className="ml-auto">
              {completeMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1"/> : <ArrowRight className="h-4 w-4 mr-1"/>}
              Generate
            </Button>
          </div>
          {genResult && (
            <div className="mt-3 flex gap-2 p-3 bg-green-50 border border-green-200 rounded text-sm text-green-800">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <div>
                <p className="font-semibold">{genResult.sheet_number} — {genResult.members_count} members, {genResult.total_weight_kg} kg</p>
                <p className="text-xs">{genResult.message}</p>
                {genResult.diameter_summary?.length > 0 && (
                  <div className="flex gap-3 mt-1 flex-wrap">
                    {genResult.diameter_summary.map((d:any)=>(
                      <span key={d.dia_mm} className="text-xs">{d.dia_mm}Ø: {d.total_weight_kg}kg</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cross-file query */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2"><Search className="h-4 w-4"/> Cross-File Data Query</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input value={queryStr} onChange={e=>setQueryStr(e.target.value)} placeholder="EB5 / C1 / all"
              className="h-8 max-w-xs" onKeyDown={e=>e.key==='Enter'&&queryMut.mutate()} />
            <Select value={memberType} onValueChange={setMemberType}>
              <SelectTrigger className="h-8 w-24"><SelectValue/></SelectTrigger>
              <SelectContent>
                {['beam','column','slab','footing'].map(t=><SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button size="sm" onClick={()=>queryMut.mutate()} disabled={!queryStr||queryMut.isPending}>
              {queryMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin"/> : <Search className="h-3.5 w-3.5"/>}
            </Button>
          </div>
          {qResult?.results?.map((r:any,i:number)=>(
            <Card key={i} className="border-blue-200">
              <CardHeader className="pb-1"><p className="text-xs font-mono font-semibold">{r.mark}</p></CardHeader>
              <CardContent className="pb-2">
                <div className="grid sm:grid-cols-2 gap-x-4">
                  {Object.entries(r.fields||{}).slice(0,16).map(([k,v]:any)=><FieldRow key={k} name={k} r={v}/>)}
                </div>
              </CardContent>
            </Card>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
