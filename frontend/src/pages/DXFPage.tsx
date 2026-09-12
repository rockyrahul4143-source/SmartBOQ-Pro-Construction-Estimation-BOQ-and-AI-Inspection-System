import { useState, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Upload, FileText, AlertCircle, CheckCircle2, Loader2,
  Info, ChevronDown, ChevronUp, Ruler, LayoutGrid,
  DoorOpen, SquareDashedBottom, AlertTriangle,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

const M2_TO_FT2 = 10.7639

function fmt(n: number, dec = 2) {
  if (!n && n !== 0) return '—'
  return n.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}

// ── KPI tile ────────────────────────────────────────
function KPI({ label, value, sub, color = '' }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className={`rounded-lg p-4 text-center border ${color || 'bg-muted/40 border-border'}`}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Diagnostic row ───────────────────────────────────
function DiagRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between py-1 border-b last:border-0 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium">{String(value)}</span>
    </div>
  )
}

export default function DXFPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [projectId,       setProjectId]       = useState('')
  const [units,           setUnits]           = useState('mm')
  const [applyMode,       setApplyMode]       = useState('false')
  const [file,            setFile]            = useState<File | null>(null)
  const [result,          setResult]          = useState<any>(null)
  const [showDiag,        setShowDiag]        = useState(false)
  const [showCandidates,  setShowCandidates]  = useState(false)

  const { data: projects } = useQuery({
    queryKey: ['projects-list'],
    queryFn:  () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data),
  })

  const uploadMut = useMutation({
    mutationFn: async () => {
      if (!file || !projectId) throw new Error('Select a project and a DXF file')
      const fd = new FormData()
      fd.append('file',              file)
      fd.append('units',             units)
      fd.append('apply_to_building', applyMode)
      return api.post(`/dxf/upload/${projectId}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: ({ data }) => {
      setResult(data)
      toast.success('DXF parsed successfully')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Upload failed'),
  })

  const { data: guide } = useQuery({
    queryKey: ['dxf-guide'],
    queryFn:  () => api.get('/dxf/layers-guide').then(r => r.data),
  })

  const ex   = result?.extracted
  const diag = result?.diagnostics ?? {}

  const hasArea      = ex && ex.building_footprint_area_m2 > 0
  const hasWalls     = ex && ex.total_wall_length_m > 0
  const hasCandidates = ex?.boundary_candidates?.length > 0
  const warnings     = result?.warnings ?? []

  return (
    <div className="space-y-5">

      {/* ── Upload card ─────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" /> Upload DXF Drawing
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Project */}
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Project *</Label>
              <Select onValueChange={setProjectId}>
                <SelectTrigger><SelectValue placeholder="Select project..." /></SelectTrigger>
                <SelectContent>
                  {(projects ?? []).map((p: any) => (
                    <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {/* Units */}
            <div className="space-y-1.5">
              <Label>Drawing Units</Label>
              <Select defaultValue="mm" onValueChange={setUnits}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {['mm','cm','m','ft','in'].map(u => (
                    <SelectItem key={u} value={u}>{u.toUpperCase()}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {/* Apply mode */}
            <div className="space-y-1.5">
              <Label>Apply to Building?</Label>
              <Select defaultValue="false" onValueChange={setApplyMode}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="false">Extract Only</SelectItem>
                  <SelectItem value="true">Extract & Apply</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Drop zone */}
          <div
            className="border-2 border-dashed border-muted-foreground/30 rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileText className="h-8 w-8 text-primary" />
                <div className="text-left">
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="h-10 w-10 text-muted-foreground/50 mx-auto mb-3" />
                <p className="text-sm font-medium">Click to select DXF file</p>
                <p className="text-xs text-muted-foreground mt-1">AutoCAD DXF format only · Max 50 MB</p>
              </>
            )}
            <input
              ref={fileRef} type="file" accept=".dxf" className="hidden"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <Button
            onClick={() => uploadMut.mutate()}
            disabled={!file || !projectId || uploadMut.isPending}
            className="w-full"
          >
            {uploadMut.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Parsing DXF...</>
              : <><Upload className="h-4 w-4 mr-2" /> Upload & Parse</>}
          </Button>
        </CardContent>
      </Card>

      {/* ── Results ─────────────────────────────────── */}
      {ex && (
        <>
          {/* Units info bar */}
          <div className="flex flex-wrap gap-3 text-sm">
            <Badge variant="outline">
              Selected units: {result.units_used?.toUpperCase()}
            </Badge>
            <Badge variant={result.units_detected === result.units_used ? 'default' : 'destructive'}>
              Auto-detected: {result.units_detected || 'unknown'}
            </Badge>
            <Badge variant="outline">
              Scale: 1 drawing unit = {result.scale_factor} m
            </Badge>
            {result.applied_to_building && (
              <Badge className="bg-green-600 text-white">
                <CheckCircle2 className="h-3 w-3 mr-1" /> Applied to building
              </Badge>
            )}
          </div>

          {/* ── Primary result — Building Footprint ───── */}
          <Card className={hasArea ? 'border-green-300' : 'border-orange-300'}>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <SquareDashedBottom className="h-5 w-5 text-primary" />
                Out-to-Out Building / Slab Area
                {!hasArea && (
                  <Badge variant="destructive" className="ml-2">Not detected</Badge>
                )}
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                External building boundary — used for slab, flooring, waterproofing BOQ
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <KPI
                  label="Building Footprint"
                  value={hasArea ? `${fmt(ex.building_footprint_area_m2)} m²` : '0'}
                  sub={hasArea ? `${fmt(ex.building_footprint_area_ft2)} ft²` : 'No boundary detected'}
                  color={hasArea ? 'bg-green-50 border-green-200' : 'bg-orange-50 border-orange-200'}
                />
                <KPI
                  label="Out-to-Out Slab Area"
                  value={hasArea ? `${fmt(ex.slab_area_m2)} m²` : '0'}
                  sub="Used in BOQ calculation"
                  color={hasArea ? 'bg-blue-50 border-blue-200' : ''}
                />
                <KPI
                  label="Boundary Perimeter"
                  value={hasArea ? `${fmt(ex.boundary_perimeter_m)} m` : '—'}
                  sub={hasArea ? `${fmt(ex.boundary_perimeter_ft)} ft` : ''}
                />
                <KPI
                  label="Boundary in ft²"
                  value={hasArea ? `${fmt(ex.building_footprint_area_ft2)} ft²` : '—'}
                  sub={hasArea ? `${fmt(ex.building_footprint_area_m2)} m²` : ''}
                />
              </div>
            </CardContent>
          </Card>

          {/* ── Walls + Openings ─────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Ruler className="h-4 w-4" /> Wall Lengths
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">External walls</span>
                    <span className="font-medium">
                      {ex.external_wall_length_m > 0 ? `${fmt(ex.external_wall_length_m)} m` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Internal walls</span>
                    <span className="font-medium">
                      {ex.internal_wall_length_m > 0 ? `${fmt(ex.internal_wall_length_m)} m` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm font-semibold border-t pt-2">
                    <span>Total wall length</span>
                    <span>{hasWalls ? `${fmt(ex.total_wall_length_m)} m` : '—'}</span>
                  </div>
                  {!hasWalls && (
                    <p className="text-xs text-muted-foreground">
                      Wall lengths not classified. Add walls on WALL/EXT_WALL/INT_WALL layers.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <DoorOpen className="h-4 w-4" /> Doors & Windows
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  <KPI label="Doors" value={String(ex.num_doors)} sub="nos" />
                  <KPI label="Windows" value={String(ex.num_windows)} sub="nos" />
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  Detected from INSERT blocks on DOOR/WINDOW layers.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* ── Boundary candidates ───────────────────── */}
          {hasCandidates && (
            <Card>
              <CardHeader
                className="pb-2 cursor-pointer"
                onClick={() => setShowCandidates(s => !s)}
              >
                <CardTitle className="text-sm flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <LayoutGrid className="h-4 w-4" />
                    Boundary Candidates ({ex.boundary_candidates.length})
                    <Badge variant="secondary" className="text-xs">
                      {ex.boundary_candidates[0]?.is_sheet_border ? 'Sheet border detected' : 'Building boundary selected'}
                    </Badge>
                  </span>
                  {showCandidates ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </CardTitle>
              </CardHeader>
              {showCandidates && (
                <CardContent>
                  <p className="text-xs text-muted-foreground mb-3">
                    Sorted by likelihood of being the building footprint. The first non-sheet-border boundary is used.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50">
                        <tr>
                          {['#', 'Area m²', 'Area ft²', 'Width m', 'Height m', 'Perimeter m', 'Sheet border?', 'Score'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {ex.boundary_candidates.map((c: any, i: number) => (
                          <tr
                            key={i}
                            className={i === 0 && !c.is_sheet_border
                              ? 'bg-green-50 font-semibold'
                              : c.is_sheet_border ? 'opacity-50' : ''}
                          >
                            <td className="px-3 py-2">
                              {i + 1}
                              {i === 0 && !c.is_sheet_border && (
                                <Badge className="ml-1 bg-green-600 text-white text-xs">Selected</Badge>
                              )}
                            </td>
                            <td className="px-3 py-2">{fmt(c.area_m2)}</td>
                            <td className="px-3 py-2">{fmt(c.area_ft2)}</td>
                            <td className="px-3 py-2">{fmt(c.width_m)}</td>
                            <td className="px-3 py-2">{fmt(c.height_m)}</td>
                            <td className="px-3 py-2">{fmt(c.perimeter_m)}</td>
                            <td className="px-3 py-2">
                              {c.is_sheet_border
                                ? <Badge variant="destructive" className="text-xs">Sheet</Badge>
                                : <Badge variant="outline" className="text-xs text-green-700">Building</Badge>}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">{fmt(c.score, 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* ── Sub-areas (rooms) ─────────────────────── */}
          {ex.rooms?.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Detected Sub-Areas ({ex.rooms.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {ex.rooms.map((r: any, i: number) => (
                    <div key={i} className="bg-blue-50 rounded p-2 text-xs">
                      <p className="font-medium">{r.name}</p>
                      <p>{fmt(r.area_m2)} m²</p>
                      <p className="text-muted-foreground">{fmt(r.area_ft2)} ft²</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── Diagnostics panel ─────────────────────── */}
          <Card>
            <CardHeader
              className="pb-2 cursor-pointer"
              onClick={() => setShowDiag(s => !s)}
            >
              <CardTitle className="text-sm flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Info className="h-4 w-4" /> DXF Diagnostics
                </span>
                {showDiag ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </CardTitle>
            </CardHeader>
            {showDiag && (
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-sm">
                  <div>
                    <p className="font-semibold mb-2 text-xs uppercase tracking-wide text-muted-foreground">Entity Counts</p>
                    <DiagRow label="Total entities"       value={diag.total_entities ?? 0} />
                    <DiagRow label="Geometric entities"   value={diag.geometric_entities ?? 0} />
                    <DiagRow label="LINE"                 value={diag.line_count ?? 0} />
                    <DiagRow label="LWPOLYLINE"           value={diag.lwpolyline_count ?? 0} />
                    <DiagRow label="POLYLINE"             value={diag.polyline_count ?? 0} />
                    <DiagRow label="ARC"                  value={diag.arc_count ?? 0} />
                    <DiagRow label="CIRCLE"               value={diag.circle_count ?? 0} />
                    <DiagRow label="SPLINE"               value={diag.spline_count ?? 0} />
                    <DiagRow label="INSERT (blocks)"      value={diag.insert_count ?? 0} />
                    <DiagRow label="OLE2FRAME"            value={diag.ole2frame_count ?? 0} />
                  </div>
                  <div>
                    <p className="font-semibold mb-2 text-xs uppercase tracking-wide text-muted-foreground">Geometry Analysis</p>
                    <DiagRow label="Segments extracted"   value={diag.segments_extracted ?? 0} />
                    <DiagRow label="Closed loops found"   value={diag.closed_loops_found ?? 0} />
                    <DiagRow label="Boundary candidates"  value={diag.boundary_candidates_count ?? 0} />
                    <DiagRow label="Snap tolerance (DU)"  value={diag.snap_tolerance_drawing_units ?? '—'} />
                    <DiagRow label="$INSUNITS value"      value={diag.insunits_value ?? 0} />
                    <DiagRow label="Scale factor (m/DU)"  value={diag.scale_factor ?? '—'} />
                    {diag.drawing_extents && (<>
                      <DiagRow label="Drawing width (DU)"  value={diag.drawing_extents.width_drawing_units} />
                      <DiagRow label="Drawing height (DU)" value={diag.drawing_extents.height_drawing_units} />
                      <DiagRow label="Drawing width (m)"   value={diag.drawing_extents.width_m} />
                      <DiagRow label="Drawing height (m)"  value={diag.drawing_extents.height_m} />
                    </>)}
                    {diag.selected_boundary && (<>
                      <DiagRow label="Selected area (m²)"  value={diag.selected_boundary.area_m2} />
                      <DiagRow label="Selected W×H (m)"    value={`${diag.selected_boundary.width_m} × ${diag.selected_boundary.height_m}`} />
                    </>)}
                  </div>
                </div>
              </CardContent>
            )}
          </Card>

          {/* ── Warnings ─────────────────────────────── */}
          {warnings.length > 0 && (
            <div className="space-y-2">
              {warnings.map((w: string, i: number) => {
                const isErr = w.startsWith('⚠') || w.toLowerCase().includes('error') || w.toLowerCase().includes('failed')
                return (
                  <div key={i} className={`flex gap-2 rounded p-3 text-sm border ${
                    isErr ? 'bg-red-50 border-red-200 text-red-800' : 'bg-yellow-50 border-yellow-200 text-yellow-800'
                  }`}>
                    {isErr ? <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> : <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />}
                    <span>{w}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* ── Applied confirmation ──────────────────── */}
          {result.applied_to_building && (
            <div className="flex gap-2 bg-green-50 border border-green-200 rounded p-3 text-sm text-green-700">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              Building dimensions updated. Run estimation to calculate BOQ quantities.
            </div>
          )}
        </>
      )}

      {/* ── Layer guide ─────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="h-4 w-4" /> DXF Layer Naming Guide
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
            {guide && Object.entries(guide)
              .filter(([k]) => k.endsWith('_layers'))
              .map(([key, vals]: any) => (
                <div key={key}>
                  <p className="font-medium capitalize mb-1">
                    {key.replace('_layers','').replace(/_/g,' ')}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {vals.map((v: string) => (
                      <Badge key={v} variant="outline" className="text-xs">{v}</Badge>
                    ))}
                  </div>
                </div>
              ))}
          </div>
          {guide?.tips && (
            <ul className="mt-4 space-y-1.5">
              {guide.tips.map((t: string, i: number) => (
                <li key={i} className="text-xs text-muted-foreground flex gap-2">
                  <span className="text-primary shrink-0">•</span>{t}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
