/**
 * BBS Files Tab — Upload drawings/schedules, query members cross-file.
 * Embedded inside BBSPage as the "Drawings & Schedules" tab.
 */
import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Upload, Trash2, Search, FileText, CheckCircle2, AlertTriangle,
  AlertCircle, Loader2, FolderOpen, Info, ArrowRight,
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
  'auto', 'beam_schedule', 'column_schedule', 'slab_schedule',
  'foundation_schedule', 'structural_plan', 'structural_plan_cad',
  'reinforcement_detail', 'section_elevation', 'general_notes', 'other',
]

function statusBadge(s: string) {
  if (s === 'complete')       return <Badge className="bg-green-600 text-white text-xs">Extracted</Badge>
  if (s === 'partial')        return <Badge className="bg-yellow-500 text-white text-xs">Partial</Badge>
  if (s === 'not_supported')  return <Badge variant="outline" className="text-xs">Manual ref</Badge>
  if (s === 'failed')         return <Badge variant="destructive" className="text-xs">Failed</Badge>
  if (s === 'pending')        return <Badge variant="secondary" className="text-xs">Pending</Badge>
  return <Badge variant="outline" className="text-xs">{s}</Badge>
}

function fieldStatus(r: any) {
  if (!r) return null
  if (r.status === 'found')
    return <span className="text-green-700 text-xs">✓ {r.source} — {r.file}</span>
  if (r.status?.startsWith('CONFLICT'))
    return <span className="text-red-700 text-xs font-semibold">⚠ CONFLICT — verify drawing</span>
  return <span className="text-orange-600 text-xs">NOT FOUND</span>
}

export default function BBSFilesTab({ projectId }: { projectId: string }) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [selFile,     setSelFile]     = useState<File | null>(null)
  const [category,    setCategory]    = useState('auto')
  const [queryStr,    setQueryStr]    = useState('')
  const [memberType,  setMemberType]  = useState('beam')
  const [queryResult, setQueryResult] = useState<any>(null)
  const [genTitle,    setGenTitle]    = useState('')
  const [genMsg,      setGenMsg]      = useState<any>(null)

  const { data: index, refetch } = useQuery({
    queryKey: ['project-files', projectId],
    queryFn:  () => api.get(`/project-files/project/${projectId}`).then(r => r.data),
    enabled:  !!projectId,
  })

  const uploadMut = useMutation({
    mutationFn: async () => {
      if (!selFile) throw new Error('No file')
      const fd = new FormData()
      fd.append('file', selFile)
      fd.append('file_category', category)
      return api.post(`/project-files/project/${projectId}/upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    onSuccess: ({ data }) => {
      qc.invalidateQueries({ queryKey: ['project-files', projectId] })
      setSelFile(null)
      const count = data.member_count || 0
      toast.success(`Uploaded — ${count} member(s) extracted`)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Upload failed'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/project-files/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-files', projectId] })
      toast.success('File removed')
    },
  })

  const queryMut = useMutation({
    mutationFn: () => api.get(
      `/project-files/project/${projectId}/query/${encodeURIComponent(queryStr)}`,
      { params: { member_type: memberType } }
    ),
    onSuccess: ({ data }) => setQueryResult(data),
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Query failed'),
  })

  const genMut = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('member_query', queryStr)
      fd.append('member_type', memberType)
      fd.append('sheet_title', genTitle || `Auto BBS — ${queryStr.toUpperCase()}`)
      return api.post(`/project-files/project/${projectId}/generate-bbs`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    onSuccess: ({ data }) => {
      setGenMsg(data)
      qc.invalidateQueries({ queryKey: ['bbs-sheets', projectId] })
      toast.success(`BBS sheet ${data.sheet_number} created — ${data.bars_created} bars`)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Generation failed'),
  })

  return (
    <div className="space-y-5">
      {/* Info box */}
      <div className="flex gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        <Info className="h-4 w-4 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold mb-0.5">Upload any structural file. The system extracts BBS data automatically.</p>
          <p className="text-xs">Supported: DXF (geometry), PDF with text layer (schedules), DWG (convert to DXF first). Multiple files are cross-searched for every query.</p>
        </div>
      </div>

      {/* Upload section */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Upload className="h-4 w-4" /> Upload Drawing / Schedule File
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2 space-y-1.5">
              <Label className="text-xs">File (DXF, PDF, DWG, Schedule)</Label>
              <div
                className="border-2 border-dashed border-muted-foreground/30 rounded-lg p-4 cursor-pointer hover:border-primary/50 text-center"
                onClick={() => fileRef.current?.click()}
              >
                {selFile
                  ? <p className="text-sm font-medium">{selFile.name} ({(selFile.size/1024).toFixed(1)} KB)</p>
                  : <><FolderOpen className="h-6 w-6 mx-auto text-muted-foreground/50 mb-1" /><p className="text-xs text-muted-foreground">Click to select any drawing or schedule file</p></>
                }
                <input ref={fileRef} type="file"
                  accept=".dxf,.dwg,.pdf,.jpg,.jpeg,.png,.xlsx,.xls,.csv"
                  className="hidden"
                  onChange={e => setSelFile(e.target.files?.[0] ?? null)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">File Category (optional)</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {FILE_CATEGORIES.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g,' ')}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button className="w-full mt-2" size="sm"
                onClick={() => uploadMut.mutate()}
                disabled={!selFile || uploadMut.isPending}>
                {uploadMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Upload className="h-4 w-4 mr-1" />}
                Upload & Extract
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Uploaded files list */}
      {index && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">
              Uploaded Files ({index.files?.length ?? 0}) — Members found: {(index.beams?.length ?? 0) + (index.columns?.length ?? 0)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!index.files?.length
              ? <p className="text-sm text-muted-foreground text-center py-6">No files uploaded yet.</p>
              : (
                <div className="space-y-2">
                  {index.files.map((f: any) => (
                    <div key={f.id} className="flex items-center gap-3 p-2.5 border rounded-lg hover:bg-muted/30">
                      <FileText className="h-5 w-5 text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{f.original_name}</p>
                        <div className="flex gap-2 flex-wrap mt-0.5">
                          <span className="text-xs text-muted-foreground">{f.file_type?.toUpperCase()}</span>
                          {f.file_category && <span className="text-xs text-muted-foreground">· {f.file_category.replace(/_/g,' ')}</span>}
                          {f.file_size_kb && <span className="text-xs text-muted-foreground">· {f.file_size_kb} KB</span>}
                          {f.member_count > 0 && <span className="text-xs text-green-700">· {f.member_count} members</span>}
                        </div>
                        {f.extraction_notes && (
                          <p className="text-xs text-yellow-700 mt-0.5 truncate">{f.extraction_notes.split('\n')[0]}</p>
                        )}
                      </div>
                      {statusBadge(f.extraction_status)}
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive shrink-0"
                        onClick={() => deleteMut.mutate(f.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              )
            }

            {/* Member index */}
            {((index.beams?.length > 0) || (index.columns?.length > 0)) && (
              <div className="mt-4 pt-3 border-t">
                <p className="text-xs font-semibold text-muted-foreground mb-2">MEMBERS FOUND ACROSS ALL FILES:</p>
                <div className="flex flex-wrap gap-1.5">
                  {index.beams?.map((m: string) => (
                    <button key={m} onClick={() => { setQueryStr(m); setMemberType('beam') }}
                      className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded hover:bg-blue-200 font-mono">
                      {m}
                    </button>
                  ))}
                  {index.columns?.map((m: string) => (
                    <button key={m} onClick={() => { setQueryStr(m); setMemberType('column') }}
                      className="text-xs px-2 py-0.5 bg-purple-100 text-purple-800 rounded hover:bg-purple-200 font-mono">
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Cross-file query */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Search className="h-4 w-4" /> Cross-File Member Query
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Search across ALL uploaded files for a member's BBS data. Examples: "EB5", "all", "C1", "EB5,EB6"
          </p>
          <div className="flex gap-2 flex-wrap">
            <Input
              value={queryStr}
              onChange={e => setQueryStr(e.target.value)}
              placeholder="EB5 / all / C1 / EB5,EB6"
              className="h-8 max-w-xs"
              onKeyDown={e => e.key === 'Enter' && queryMut.mutate()}
            />
            <Select value={memberType} onValueChange={setMemberType}>
              <SelectTrigger className="h-8 w-28"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="beam">Beam</SelectItem>
                <SelectItem value="column">Column</SelectItem>
                <SelectItem value="slab">Slab</SelectItem>
              </SelectContent>
            </Select>
            <Button size="sm" onClick={() => queryMut.mutate()} disabled={!queryStr || queryMut.isPending}>
              {queryMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Search className="h-4 w-4 mr-1" />}
              Find Data
            </Button>
          </div>

          {/* Query results — extraction review */}
          {queryResult && (
            <div className="space-y-3 mt-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">
                  Found {queryResult.count} member(s) across {queryResult.file_count ?? '?'} file(s)
                </p>
                {queryResult.count > 0 && (
                  <div className="flex gap-2 items-center">
                    <Input
                      value={genTitle}
                      onChange={e => setGenTitle(e.target.value)}
                      placeholder="Sheet title (optional)"
                      className="h-7 text-xs w-44"
                    />
                    <Button size="sm" onClick={() => genMut.mutate()} disabled={genMut.isPending}
                      className="bg-green-700 hover:bg-green-800 text-white">
                      {genMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <ArrowRight className="h-3.5 w-3.5 mr-1" />}
                      Generate BBS Sheet
                    </Button>
                  </div>
                )}
              </div>

              {genMsg && (
                <div className="flex gap-2 p-3 bg-green-50 border border-green-200 rounded text-sm text-green-800">
                  <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">{genMsg.sheet_number} created — {genMsg.bars_created} bars, {genMsg.total_weight_kg} kg</p>
                    <p className="text-xs mt-0.5">{genMsg.message}</p>
                  </div>
                </div>
              )}

              {queryResult.results?.map((res: any, i: number) => (
                <Card key={i} className="border-blue-200">
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <span className="font-mono text-primary">{res.mark}</span>
                      <Badge variant="outline" className="text-xs">{res.member_type}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
                      {Object.entries(res.fields || {}).map(([fn, fv]: any) => (
                        <div key={fn} className="flex items-start justify-between gap-2 text-sm border-b pb-1">
                          <span className="text-muted-foreground text-xs w-36 shrink-0">{fn.replace(/_/g,' ')}</span>
                          <div className="text-right">
                            {fv.status === 'found'
                              ? <span className="font-mono font-medium">{typeof fv.value === 'object' ? JSON.stringify(fv.value) : String(fv.value ?? '—')}</span>
                              : fv.status?.startsWith('CONFLICT')
                                ? <span className="text-red-600 text-xs font-semibold">⚠ CONFLICT</span>
                                : <span className="text-orange-500 text-xs">NOT FOUND</span>
                            }
                            <div>{fieldStatus(fv)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    {Object.keys(res.fields || {}).length === 0 && (
                      <div className="flex gap-2 p-3 bg-orange-50 border border-orange-200 rounded text-sm text-orange-800">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        <div>
                          <p className="font-semibold">No data found for {res.mark}</p>
                          <p className="text-xs mt-0.5">This member was not found in any uploaded file. Upload the relevant beam/column schedule or enter values manually in the Manual BBS tab.</p>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}

              <p className="text-xs text-muted-foreground">
                Files searched: {queryResult.files_searched?.join(', ')}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
