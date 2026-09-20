/**
 * DXFPage.tsx — v4
 * =================
 * DXF upload + exact area extraction UI.
 *
 * New in v4
 * ---------
 * - Multi-building cards (Building A, B, C …)
 * - Total area when multiple buildings detected
 * - DWG rejection card with conversion instructions
 * - OLE-only error card with AutoCAD fix steps
 * - SVG boundary preview (click candidates to change)
 * - Full diagnostics: entity counts, geometry analysis, selected boundary
 * - All warnings colour-coded (red / amber / green)
 */

import { useState, useRef, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Upload, FileText, AlertCircle, CheckCircle2, Loader2, Info,
  ChevronDown, ChevronUp, Ruler, DoorOpen, SquareDashedBottom,
  XCircle, Layers, BarChart3, Grid3X3, Building2, ArrowRight,
} from 'lucide-react'
import api from '@/lib/api'
import { Button }   from '@/components/ui/button'
import { Label }    from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

// ── helpers ────────────────────────────────────────────────────────────────────
const M2_TO_FT2 = 10.7639
const MAX_MB    = Number(import.meta.env?.VITE_MAX_FILE_SIZE_MB ?? 50) || 50

function fmt(n?: number | null, dec = 2): string {
  if (n == null || isNaN(n)) return '—'
  return n.toLocaleString('en-IN', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  })
}

// ── tiny components ─────────────────────────────────────────────────────────────
function KPI({
  label, value, sub, color = 'bg-muted/40 border-border', large,
}: {
  label: string; value: string; sub?: string; color?: string; large?: boolean
}) {
  return (
    <div className={`rounded-xl p-4 text-center border ${color}`}>
      <p className="text-xs text-muted-foreground leading-tight">{label}</p>
      <p className={`font-bold mt-1 ${large ? 'text-2xl' : 'text-lg'}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

function DiagRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between py-1 border-b last:border-0 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium tabular-nums">{String(value)}</span>
    </div>
  )
}

function WarnAlert({ msg }: { msg: string }) {
  const isErr = /^⚠|error|failed|cannot|ole2frame|no geometry|no vector/i.test(msg)
  const isOk  = /confirmed|applied|stripped|preserved/i.test(msg)
  const cls   = isOk  ? 'bg-green-50 border-green-200 text-green-800'
              : isErr ? 'bg-red-50 border-red-200 text-red-800'
              :         'bg-amber-50 border-amber-200 text-amber-800'
  const Icon  = isOk ? CheckCircle2 : isErr ? XCircle : AlertCircle
  return (
    <div className={`flex gap-2 rounded-lg p-3 text-sm border ${cls}`}>
      <Icon className="h-4 w-4 shrink-0 mt-0.5" />
      <span className="whitespace-pre-wrap">{msg}</span>
    </div>
  )
}

function Section({
  title, icon: Icon, badge, open, onToggle, children,
}: {
  title: string; icon: any; badge?: React.ReactNode
  open: boolean; onToggle: () => void; children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader className="pb-2 cursor-pointer select-none" onClick={onToggle}>
        <CardTitle className="text-sm flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-primary" />
            {title}
            {badge}
          </span>
          {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </CardTitle>
      </CardHeader>
      {open && <CardContent>{children}</CardContent>}
    </Card>
  )
}

// ── SVG boundary preview ────────────────────────────────────────────────────────
interface Candidate {
  area_m2: number; area_ft2: number
  perimeter_m: number; perimeter_ft: number
  width_m: number; height_m: number; pts_count?: number
  is_sheet_border: boolean; is_selected?: boolean
  score: number; svg_path?: string; svg_viewbox?: string
  etype?: string; layer?: string
}

function SVGPreview({
  candidates, selectedIdx, viewbox, onSelect,
}: {
  candidates: Candidate[]; selectedIdx: number
  viewbox: string; onSelect: (i: number) => void
}) {
  if (!candidates?.length) return null
  const [vbx, vby, vbW, vbH] = viewbox.split(' ').map(Number)
  return (
    <div className="relative w-full rounded-xl overflow-hidden border bg-slate-50">
      <div className="absolute top-2 left-2 z-10">
        <Badge className="bg-slate-800/80 text-white text-xs backdrop-blur-sm">
          Detected Boundary Preview
        </Badge>
      </div>
      <svg viewBox={viewbox} className="w-full" style={{ maxHeight: 340 }}
           xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="dxf-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M20 0L0 0 0 20" fill="none" stroke="#e2e8f0" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width={vbW} height={vbH} fill="url(#dxf-grid)" />
        {candidates.map((c, i) => {
          if (!c.svg_path || i === selectedIdx) return null
          return (
            <path key={i} d={c.svg_path}
              fill="rgba(148,163,184,0.10)" stroke="#94a3b8"
              strokeWidth="1" strokeDasharray="4 3"
              className="cursor-pointer hover:fill-blue-100/40 transition-all"
              onClick={() => onSelect(i)}
            />
          )
        })}
        {candidates[selectedIdx]?.svg_path && (
          <path d={candidates[selectedIdx].svg_path}
            fill="rgba(34,197,94,0.18)" stroke="#16a34a"
            strokeWidth="2.5" strokeLinejoin="round"/>
        )}
      </svg>
      <div className="absolute bottom-2 right-2 flex gap-2">
        <span className="flex items-center gap-1 text-xs bg-white/90 rounded px-2 py-0.5 border">
          <span className="inline-block w-3 h-0.5 bg-green-600"/> Selected
        </span>
        {candidates.length > 1 && (
          <span className="flex items-center gap-1 text-xs bg-white/90 rounded px-2 py-0.5 border">
            <span className="inline-block w-3 h-0.5 bg-slate-400 border-dashed"/> Other
          </span>
        )}
      </div>
    </div>
  )
}

// ── Candidates table ────────────────────────────────────────────────────────────
function CandidateTable({
  candidates, selectedIdx, onSelect, isPending,
}: {
  candidates: Candidate[]; selectedIdx: number
  onSelect: (i: number) => void; isPending: boolean
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/60 text-xs text-muted-foreground">
            {['#','Area m²','ft²','W × H (m)','Perimeter','Type','Source',''].map(h => (
              <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {candidates.map((c, i) => {
            const isSel = i === selectedIdx
            return (
              <tr key={i}
                className={isSel ? 'bg-green-50 font-semibold'
                  : c.is_sheet_border ? 'opacity-50 bg-slate-50'
                  : 'hover:bg-muted/30 cursor-pointer'}
                onClick={() => !c.is_sheet_border && onSelect(i)}
              >
                <td className="px-3 py-2.5 whitespace-nowrap">
                  <span className="font-mono text-xs">{i + 1}</span>
                  {isSel && (
                    <Badge className="ml-1.5 bg-green-600 text-white text-xs py-0">✓</Badge>
                  )}
                  {!isSel && i === 0 && !c.is_sheet_border && (
                    <Badge variant="outline" className="ml-1.5 text-xs py-0 border-green-400 text-green-700">
                      Recommended
                    </Badge>
                  )}
                </td>
                <td className="px-3 py-2.5 tabular-nums">{fmt(c.area_m2)}</td>
                <td className="px-3 py-2.5 tabular-nums text-muted-foreground">{fmt(c.area_ft2)}</td>
                <td className="px-3 py-2.5 tabular-nums">{fmt(c.width_m)} × {fmt(c.height_m)}</td>
                <td className="px-3 py-2.5 tabular-nums">{fmt(c.perimeter_m)} m</td>
                <td className="px-3 py-2.5">
                  {c.is_sheet_border
                    ? <Badge variant="destructive" className="text-xs">Sheet</Badge>
                    : <Badge variant="outline" className="text-xs text-green-700 border-green-300">Building</Badge>}
                </td>
                <td className="px-3 py-2.5 text-xs text-muted-foreground">{c.etype ?? '—'}</td>
                <td className="px-3 py-2.5">
                  {!c.is_sheet_border && !isSel && (
                    <Button size="sm" variant="outline" className="h-6 text-xs px-2"
                      disabled={isPending}
                      onClick={e => { e.stopPropagation(); onSelect(i) }}>
                      Use this
                    </Button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────────
export default function DXFPage() {
  const fileRef = useRef<HTMLInputElement>(null)

  const [projectId, setProjectId] = useState('')
  const [units,     setUnits]     = useState('mm')
  const [applyMode, setApplyMode] = useState('false')
  const [file,      setFile]      = useState<File | null>(null)
  const [result,    setResult]    = useState<any>(null)
  const [selIdx,    setSelIdx]    = useState(0)

  const [showDiag,       setShowDiag]       = useState(false)
  const [showCandidates, setShowCandidates] = useState(true)
  const [showRooms,      setShowRooms]      = useState(false)
  const [showGuide,      setShowGuide]      = useState(false)

  const { data: projects } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data ?? []),
  })
  const { data: guide } = useQuery({
    queryKey: ['dxf-guide'],
    queryFn: () => api.get('/dxf/layers-guide').then(r => r.data),
  })

  const uploadMut = useMutation({
    mutationFn: async (overrideIdx: number = -1) => {
      if (!file)      throw new Error('Select a DXF file first')
      if (!projectId) throw new Error('Select a project first')
      const fd = new FormData()
      fd.append('file',              file)
      fd.append('units',             units)
      fd.append('apply_to_building', applyMode)
      fd.append('selected_boundary', String(overrideIdx))
      return api.post(`/dxf/upload/${projectId}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: ({ data }) => {
      setResult(data)
      const cands = data.extracted?.boundary_candidates ?? []
      const auto  = cands.findIndex((c: Candidate) => c.is_selected)
      setSelIdx(auto >= 0 ? auto : 0)
      toast.success('DXF parsed successfully')
    },
    onError: (e: any) =>
      toast.error(e.response?.data?.detail ?? e.message ?? 'Upload failed'),
  })

  const handleSelectBoundary = useCallback((idx: number) => {
    setSelIdx(idx)
    if (result) uploadMut.mutate(idx)
  }, [result])

  const ex         = result?.extracted
  const diag       = result?.diagnostics ?? {}
  const warnings   = result?.warnings    ?? []
  const candidates = (ex?.boundary_candidates ?? []) as Candidate[]
  const rooms      = (ex?.rooms ?? []) as any[]
  const buildings  = (ex?.buildings ?? []) as any[]

  const hasArea    = ex && ex.building_footprint_area_m2 > 0
  const hasWalls   = ex && ex.total_wall_length_m > 0
  const hasExtWall = ex && ex.external_wall_length_m > 0
  const hasIntWall = ex && ex.internal_wall_length_m > 0
  const hasOLE     = (diag.ole2frame_count ?? 0) > 0
  const hasGeo     = (diag.geometric_entities ?? 0) > 0 || (diag.segments_extracted ?? 0) > 0
  const viewbox    = ex?.svg_viewbox ?? '0 0 480 320'
  const selBnd     = diag.selected_boundary ?? {}
  const unitsMatch = result?.units_detected === result?.units_used
  const isOleOnly  = hasOLE && !hasGeo && !hasArea
  const multiBuilding = buildings.length >= 2

  return (
    <div className="space-y-5 max-w-6xl mx-auto">

      {/* ── Upload card ──────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Upload className="h-5 w-5 text-primary"/>
            Upload AutoCAD DXF Drawing
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Extracts exact out-to-out building footprint area (same as AutoCAD AREA command),
            wall lengths, doors and windows from DXF files.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Project <span className="text-destructive">*</span></Label>
              <Select onValueChange={setProjectId}>
                <SelectTrigger><SelectValue placeholder="Select project…"/></SelectTrigger>
                <SelectContent>
                  {(projects ?? []).map((p: any) => (
                    <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Drawing Units</Label>
              <Select defaultValue="mm" onValueChange={setUnits}>
                <SelectTrigger><SelectValue/></SelectTrigger>
                <SelectContent>
                  {[
                    {v:'mm',l:'Millimeters (mm)'},{v:'cm',l:'Centimeters (cm)'},
                    {v:'m', l:'Meters (m)'},{v:'ft',l:'Feet (ft)'},{v:'in',l:'Inches (in)'},
                  ].map(u => <SelectItem key={u.v} value={u.v}>{u.l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Apply to Building?</Label>
              <Select defaultValue="false" onValueChange={setApplyMode}>
                <SelectTrigger><SelectValue/></SelectTrigger>
                <SelectContent>
                  <SelectItem value="false">Extract Only</SelectItem>
                  <SelectItem value="true">Extract &amp; Apply</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Drop zone */}
          <div
            className="border-2 border-dashed border-muted-foreground/30 rounded-xl p-8 text-center cursor-pointer hover:border-primary/60 hover:bg-primary/[0.02] transition-all"
            onClick={() => fileRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              const f = e.dataTransfer.files[0]
              if (f) { setFile(f); setResult(null) }
            }}
          >
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <div className="bg-primary/10 rounded-lg p-2">
                  <FileText className="h-8 w-8 text-primary"/>
                </div>
                <div className="text-left">
                  <p className="font-semibold">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size/1024).toFixed(1)} KB
                    <button className="ml-2 text-xs text-destructive underline"
                      onClick={e => { e.stopPropagation(); setFile(null); setResult(null) }}>
                      Remove
                    </button>
                  </p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3"/>
                <p className="text-sm font-medium">Drop DXF file here or click to browse</p>
                <p className="text-xs text-muted-foreground mt-1">
                  AutoCAD DXF format only · Max {MAX_MB} MB
                </p>
                <p className="text-xs text-amber-600 mt-1">
                  DWG files must be converted to DXF first (File → Save As → DXF in AutoCAD)
                </p>
              </>
            )}
            <input ref={fileRef} type="file" accept=".dxf" className="hidden"
              onChange={e => { setFile(e.target.files?.[0] ?? null); setResult(null) }}/>
          </div>

          <Button
            onClick={() => uploadMut.mutate(-1)}
            disabled={!file || !projectId || uploadMut.isPending}
            className="w-full h-11"
          >
            {uploadMut.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin mr-2"/>Parsing DXF…</>
              : <><Upload className="h-4 w-4 mr-2"/>Upload &amp; Parse DXF</>}
          </Button>
        </CardContent>
      </Card>

      {/* ── OLE-only error card ──────────────────────────────────────────────── */}
      {ex && isOleOnly && (
        <Card className="border-red-300 bg-red-50">
          <CardContent className="pt-5">
            <div className="flex gap-3">
              <XCircle className="h-6 w-6 text-red-500 shrink-0 mt-0.5"/>
              <div className="space-y-2">
                <p className="font-semibold text-red-800">
                  OLE Embedded Object — No Vector Geometry
                </p>
                <p className="text-sm text-red-700">
                  This DXF contains an embedded bitmap (OLE2FRAME) but no vector CAD geometry.
                  Area cannot be calculated.
                </p>
                <div className="bg-white border border-red-200 rounded-lg p-3 text-sm text-red-800 space-y-1">
                  <p className="font-medium">Fix in AutoCAD:</p>
                  <ol className="list-decimal list-inside space-y-0.5 text-red-700 text-xs">
                    <li>Open the file in AutoCAD</li>
                    <li>Type <code className="bg-red-100 px-1 rounded">EXPLODE</code> → select the OLE frame → Enter</li>
                    <li><strong>File → Save As → AutoCAD 2010 DXF (ASCII)</strong></li>
                    <li>Re-upload the new .dxf file</li>
                  </ol>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Results ──────────────────────────────────────────────────────────── */}
      {ex && (
        <>
          {/* Units bar */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="outline" className="gap-1">
              <Ruler className="h-3 w-3"/> Selected: {(result.units_used ?? '').toUpperCase()}
            </Badge>
            <Badge variant={unitsMatch ? 'secondary' : 'destructive'} className="gap-1">
              Auto-detected: {result.units_detected || 'unknown'}{!unitsMatch && ' ⚠'}
            </Badge>
            <Badge variant="outline">Scale: 1 DU = {result.scale_factor} m</Badge>
            {result.file_size_kb && (
              <Badge variant="outline">File: {result.file_size_kb} KB</Badge>
            )}
            {result.applied_to_building && (
              <Badge className="bg-green-600 text-white gap-1">
                <CheckCircle2 className="h-3 w-3"/> Applied to building
              </Badge>
            )}
          </div>

          {/* ── Primary footprint card ─────────────────────────────────────── */}
          <Card className={hasArea ? 'border-green-300' : 'border-orange-300'}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <SquareDashedBottom className="h-5 w-5 text-primary"/>
                    Out-to-Out Building / Slab Area
                    {!hasArea && <Badge variant="destructive" className="ml-1">Not detected</Badge>}
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    External building boundary — primary value for slab, flooring, waterproofing BOQ
                  </p>
                </div>
                {hasArea && (
                  <Badge className="bg-green-100 text-green-800 border border-green-300 shrink-0">
                    ✓ Detected
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <KPI label="Building Footprint"
                  value={hasArea ? `${fmt(ex.building_footprint_area_m2)} m²` : '0 m²'}
                  sub={hasArea ? `${fmt(ex.building_footprint_area_ft2)} ft²` : 'No boundary detected'}
                  color={hasArea ? 'bg-green-50 border-green-200' : 'bg-orange-50 border-orange-200'}
                  large/>
                <KPI label="Slab Area (BOQ)"
                  value={hasArea ? `${fmt(ex.slab_area_m2)} m²` : '0 m²'}
                  sub="Used in BOQ calculations"
                  color={hasArea ? 'bg-blue-50 border-blue-200' : ''}/>
                <KPI label="Boundary Perimeter"
                  value={hasArea ? `${fmt(ex.boundary_perimeter_m)} m` : '—'}
                  sub={hasArea ? `${fmt(ex.boundary_perimeter_ft)} ft` : ''}/>
                <KPI label="Footprint ft²"
                  value={hasArea ? `${fmt(ex.building_footprint_area_ft2)} ft²` : '—'}
                  sub={hasArea ? `${fmt(ex.building_footprint_area_m2)} m²` : ''}/>
              </div>

              {selBnd.width_m > 0 && selBnd.height_m > 0 && (
                <div className="flex items-center gap-3 text-sm bg-muted/40 rounded-lg px-4 py-2.5">
                  <span className="text-muted-foreground">Boundary dimensions:</span>
                  <span className="font-semibold">
                    {fmt(selBnd.width_m)} m × {fmt(selBnd.height_m)} m
                  </span>
                  <ArrowRight className="h-3 w-3 text-muted-foreground"/>
                  <span className="text-muted-foreground">
                    {fmt(selBnd.width_m * 3.28084)} ft × {fmt(selBnd.height_m * 3.28084)} ft
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── Multi-building cards ──────────────────────────────────────────── */}
          {multiBuilding && (
            <Card className="border-blue-200">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Building2 className="h-5 w-5 text-blue-600"/>
                  Multiple Buildings Detected ({buildings.length})
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Each closed boundary is reported separately.
                  Total combined area:{' '}
                  <strong>
                    {fmt(buildings.reduce((s: number, b: any) => s + b.area_m2, 0))} m²
                  </strong>
                </p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {buildings.map((b: any, i: number) => (
                    <div key={i}
                      className="rounded-xl border bg-blue-50 border-blue-200 p-4 space-y-2">
                      <p className="font-semibold text-blue-800 text-sm">{b.label}</p>
                      <div className="grid grid-cols-2 gap-1 text-xs">
                        <div>
                          <p className="text-muted-foreground">Area</p>
                          <p className="font-bold text-base">{fmt(b.area_m2)} m²</p>
                          <p className="text-muted-foreground">{fmt(b.area_ft2)} ft²</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Perimeter</p>
                          <p className="font-medium">{fmt(b.perimeter_m)} m</p>
                          <p className="text-muted-foreground">
                            {fmt(b.width_m)} × {fmt(b.height_m)} m
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex items-center gap-3 bg-blue-100 rounded-lg px-4 py-2.5 text-sm">
                  <span className="text-blue-700">Total combined area:</span>
                  <span className="font-bold text-blue-900">
                    {fmt(buildings.reduce((s: number, b: any) => s + b.area_m2, 0))} m²
                  </span>
                  <span className="text-blue-600">
                    = {fmt(buildings.reduce((s: number, b: any) => s + b.area_ft2, 0))} ft²
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── SVG Preview ───────────────────────────────────────────────────── */}
          {candidates.length > 0 && (
            <SVGPreview candidates={candidates} selectedIdx={selIdx}
              viewbox={viewbox} onSelect={handleSelectBoundary}/>
          )}

          {/* ── Boundary candidates ────────────────────────────────────────────── */}
          {candidates.length > 0 && (
            <Section title={`Boundary Candidates (${candidates.length})`} icon={Grid3X3}
              badge={candidates.length > 1
                ? <Badge variant="secondary" className="text-xs">Click row to change</Badge>
                : null}
              open={showCandidates} onToggle={() => setShowCandidates(s => !s)}
            >
              <p className="text-xs text-muted-foreground mb-3">
                First non-sheet-border is auto-selected. Click any row or "Use this" to override.
              </p>
              <CandidateTable candidates={candidates} selectedIdx={selIdx}
                onSelect={handleSelectBoundary} isPending={uploadMut.isPending}/>
              {uploadMut.isPending && (
                <div className="flex items-center gap-2 mt-3 text-sm text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin"/> Re-parsing…
                </div>
              )}
            </Section>
          )}

          {/* ── Walls + Openings ──────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Ruler className="h-4 w-4 text-primary"/> Wall Lengths
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">External walls</span>
                    <span className="font-medium">
                      {hasExtWall ? `${fmt(ex.external_wall_length_m)} m` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Internal walls</span>
                    <span className="font-medium">
                      {hasIntWall ? `${fmt(ex.internal_wall_length_m)} m` : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm font-semibold border-t pt-2">
                    <span>Total</span>
                    <span>{hasWalls ? `${fmt(ex.total_wall_length_m)} m` : '—'}</span>
                  </div>
                </div>
                {!hasExtWall && !hasIntWall && hasWalls && (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded p-2">
                    No WALL layers — total shows all line geometry.
                    Use WALL / EXT_WALL / INT_WALL layers for breakdown.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <DoorOpen className="h-4 w-4 text-primary"/> Doors &amp; Windows
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <KPI label="Doors"   value={String(ex.num_doors ?? 0)}   sub="Nos."
                    color={ex.num_doors > 0 ? 'bg-blue-50 border-blue-200' : ''}/>
                  <KPI label="Windows" value={String(ex.num_windows ?? 0)} sub="Nos."
                    color={ex.num_windows > 0 ? 'bg-indigo-50 border-indigo-200' : ''}/>
                </div>
                <p className="text-xs text-muted-foreground">
                  Detected from INSERT blocks on DOOR / WINDOW layers.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* ── Sub-areas ──────────────────────────────────────────────────────── */}
          {rooms.length > 0 && (
            <Section title={`Sub-Areas / Rooms (${rooms.length})`} icon={BarChart3}
              open={showRooms} onToggle={() => setShowRooms(s => !s)}
            >
              <p className="text-xs text-muted-foreground mb-3">
                Closed boundaries smaller than the building footprint — likely rooms or zones.
                Primary BOQ area is the out-to-out footprint above.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                {rooms.map((r: any, i: number) => (
                  <div key={i}
                    className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs">
                    <p className="font-semibold text-blue-800">{r.name}</p>
                    <p className="text-blue-700 mt-0.5">{fmt(r.area_m2)} m²</p>
                    <p className="text-muted-foreground">{fmt(r.area_ft2)} ft²</p>
                    {r.width_m > 0 && (
                      <p className="text-muted-foreground mt-0.5">
                        {fmt(r.width_m)} × {fmt(r.height_m)} m
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* ── Diagnostics ────────────────────────────────────────────────────── */}
          <Section title="DXF Diagnostics" icon={Info}
            badge={
              <Badge variant={hasGeo ? 'secondary' : 'destructive'} className="text-xs">
                {diag.segments_extracted ?? 0} segments · {diag.direct_valid_polys ?? 0} direct polys
              </Badge>
            }
            open={showDiag} onToggle={() => setShowDiag(s => !s)}
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-2">Entity Counts</p>
                <DiagRow label="Total entities"     value={diag.total_entities ?? 0}/>
                <DiagRow label="Geometric entities" value={diag.geometric_entities ?? 0}/>
                <DiagRow label="LINE"               value={diag.line_count ?? 0}/>
                <DiagRow label="LWPOLYLINE"         value={diag.lwpolyline_count ?? 0}/>
                <DiagRow label="POLYLINE"           value={diag.polyline_count ?? 0}/>
                <DiagRow label="ARC"                value={diag.arc_count ?? 0}/>
                <DiagRow label="CIRCLE"             value={diag.circle_count ?? 0}/>
                <DiagRow label="SPLINE"             value={diag.spline_count ?? 0}/>
                <DiagRow label="HATCH"              value={diag.hatch_count ?? 0}/>
                <DiagRow label="INSERT (blocks)"    value={diag.insert_count ?? 0}/>
                <DiagRow label="OLE2FRAME"          value={diag.ole2frame_count ?? 0}/>
              </div>
              <div>
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-2">Geometry Analysis</p>
                <DiagRow label="Segments extracted"   value={diag.segments_extracted ?? 0}/>
                <DiagRow label="Direct closed polys"  value={diag.direct_closed_polys ?? 0}/>
                <DiagRow label="Direct valid polys"   value={diag.direct_valid_polys ?? 0}/>
                <DiagRow label="Chain loops (LINE)"   value={diag.chain_loops_found ?? 0}/>
                <DiagRow label="Boundary candidates"  value={diag.boundary_candidates ?? 0}/>
                <DiagRow label="Snap tolerance (DU)"  value={diag.snap_tolerance_du ?? '—'}/>
                <DiagRow label="$INSUNITS value"      value={diag.insunits_value ?? 0}/>
                <DiagRow label="Scale factor (m/DU)"  value={diag.scale_factor_m_per_du ?? '—'}/>
                {diag.drawing_extents && (<>
                  <DiagRow label="Drawing width (DU)"  value={diag.drawing_extents.width_du}/>
                  <DiagRow label="Drawing height (DU)" value={diag.drawing_extents.height_du}/>
                  <DiagRow label="Drawing width (m)"   value={diag.drawing_extents.width_m}/>
                  <DiagRow label="Drawing height (m)"  value={diag.drawing_extents.height_m}/>
                </>)}
              </div>
              <div>
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-2">Selected Boundary</p>
                {selBnd.area_m2 != null ? (<>
                  <DiagRow label="Area (m²)"     value={selBnd.area_m2}/>
                  <DiagRow label="Area (ft²)"    value={selBnd.area_ft2}/>
                  <DiagRow label="Perimeter (m)" value={selBnd.perimeter_m}/>
                  <DiagRow label="Width (m)"     value={selBnd.width_m}/>
                  <DiagRow label="Height (m)"    value={selBnd.height_m}/>
                  <DiagRow label="Source"        value={selBnd.etype ?? '—'}/>
                  <DiagRow label="Layer"         value={selBnd.layer ?? '—'}/>
                </>) : (
                  <p className="text-sm text-muted-foreground">No boundary selected</p>
                )}
              </div>
            </div>
          </Section>

          {/* ── Warnings ───────────────────────────────────────────────────────── */}
          {warnings.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Parser Messages
              </p>
              {warnings.map((w: string, i: number) => <WarnAlert key={i} msg={w}/>)}
            </div>
          )}

          {/* ── Applied confirmation ───────────────────────────────────────────── */}
          {result.applied_to_building && (
            <div className="flex gap-3 bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-700">
              <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5"/>
              <div>
                <p className="font-semibold">Building dimensions updated.</p>
                <p className="text-green-600 mt-0.5">
                  Slab area, wall lengths and opening counts written to building.
                  Go to <strong>Estimation</strong> and run to generate BOQ quantities.
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Layer guide ──────────────────────────────────────────────────────── */}
      <Section title="DXF Layer Naming Guide" icon={Layers}
        open={showGuide} onToggle={() => setShowGuide(s => !s)}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
          {guide && Object.entries(guide)
            .filter(([k]) => k.endsWith('_layers'))
            .map(([key, vals]: any) => (
              <div key={key}>
                <p className="font-semibold capitalize mb-1.5 text-xs">
                  {key.replace('_layers','').replace(/_/g,' ')} layers
                </p>
                <div className="flex flex-wrap gap-1">
                  {vals.map((v: string) => (
                    <Badge key={v} variant="outline" className="text-xs font-mono">{v}</Badge>
                  ))}
                </div>
              </div>
            ))}
        </div>
        {guide?.tips && (
          <ul className="mt-5 space-y-2">
            {guide.tips.map((t: string, i: number) => (
              <li key={i} className="text-xs text-muted-foreground flex gap-2">
                <span className="text-primary shrink-0 font-bold">•</span>{t}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}
