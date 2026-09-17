/**
 * DXFPage.tsx — v3
 * ==================
 * Full DXF upload + area extraction UI.
 *
 * Features:
 *  - Upload form with project / unit / apply-mode selectors
 *  - Out-to-out building footprint KPI cards
 *  - SVG boundary preview with highlighted selected loop
 *  - Interactive boundary candidate selector (click to change selection)
 *  - Expanded wall / door / window cards
 *  - Sub-areas (room outline) grid
 *  - Full diagnostics panel (entity counts, extents, loop stats)
 *  - Contextual warnings with severity colouring
 *  - OLE2FRAME / no-geometry error states with fix instructions
 *  - "Applied to building" confirmation banner
 *  - Layer naming guide
 */

import { useState, useRef, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Upload, FileText, AlertCircle, CheckCircle2, Loader2, Info,
  ChevronDown, ChevronUp, Ruler, DoorOpen, SquareDashedBottom,
  AlertTriangle, XCircle, Layers, BarChart3, Grid3X3, RefreshCw,
  ArrowRight,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

// ── Constants ──────────────────────────────────────────────────────────────────
const SVG_W = 480
const SVG_H = 320

// ── Formatters ─────────────────────────────────────────────────────────────────
function fmt(n: number | null | undefined, dec = 2): string {
  if (n == null || isNaN(n as number)) return '—'
  return (n as number).toLocaleString('en-IN', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  })
}

function fmtUnit(n: number | null | undefined, unit: string, dec = 2): string {
  return `${fmt(n, dec)} ${unit}`
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface KPIProps {
  label: string
  value: string
  sub?: string
  colorClass?: string
  large?: boolean
}
function KPI({ label, value, sub, colorClass = 'bg-muted/40 border-border', large }: KPIProps) {
  return (
    <div className={`rounded-xl p-4 text-center border ${colorClass}`}>
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

// ── SVG Boundary Preview ────────────────────────────────────────────────────────
interface SVGPreviewProps {
  candidates: Candidate[]
  selectedIdx: number
  viewbox: string
  onSelect: (idx: number) => void
}

function SVGPreview({ candidates, selectedIdx, viewbox, onSelect }: SVGPreviewProps) {
  if (!candidates?.length) return null

  const vbParts = viewbox.split(' ').map(Number)
  const vbW = vbParts[2] || SVG_W
  const vbH = vbParts[3] || SVG_H

  return (
    <div className="relative w-full rounded-xl overflow-hidden border bg-slate-50">
      <div className="absolute top-2 left-2 z-10">
        <Badge className="bg-slate-800/80 text-white text-xs backdrop-blur-sm">
          Building Boundary Preview
        </Badge>
      </div>
      <svg
        viewBox={viewbox}
        className="w-full"
        style={{ maxHeight: '340px' }}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Grid background */}
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e2e8f0" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width={vbW} height={vbH} fill="url(#grid)" />

        {/* Non-selected candidates — draw first (background) */}
        {candidates.map((c, i) => {
          if (i === selectedIdx || !c.svg_path) return null
          return (
            <path
              key={i}
              d={c.svg_path}
              fill="rgba(148,163,184,0.10)"
              stroke="#94a3b8"
              strokeWidth="1"
              strokeDasharray="4 3"
              className="cursor-pointer hover:fill-blue-100/30 hover:stroke-blue-400 transition-all"
              onClick={() => onSelect(i)}
            />
          )
        })}

        {/* Selected / recommended candidate — draw on top */}
        {candidates[selectedIdx]?.svg_path && (
          <path
            d={candidates[selectedIdx].svg_path}
            fill="rgba(34,197,94,0.15)"
            stroke="#16a34a"
            strokeWidth="2.5"
            strokeLinejoin="round"
          />
        )}

        {/* Centroid label for selected */}
        {candidates[selectedIdx]?.svg_path && (() => {
          // Rough centroid from SVG path: parse first M x y
          const m = candidates[selectedIdx].svg_path.match(/M\s*([\d.]+)\s+([\d.]+)/)
          if (!m) return null
          return (
            <text
              x={Number(m[1])}
              y={Number(m[2]) - 6}
              fontSize="10"
              fill="#15803d"
              fontWeight="bold"
              textAnchor="middle"
            >
              {fmt(candidates[selectedIdx].area_m2)} m²
            </text>
          )
        })()}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 right-2 flex gap-2">
        <span className="flex items-center gap-1 text-xs bg-white/90 rounded px-2 py-0.5 border">
          <span className="w-3 h-0.5 bg-green-600 inline-block" /> Selected
        </span>
        {candidates.length > 1 && (
          <span className="flex items-center gap-1 text-xs bg-white/90 rounded px-2 py-0.5 border">
            <span className="w-3 h-0.5 bg-slate-400 inline-block border-dashed" /> Other
          </span>
        )}
      </div>
    </div>
  )
}

// ── Boundary Candidate Row ──────────────────────────────────────────────────────
interface Candidate {
  area_m2: number
  area_ft2: number
  perimeter_m: number
  perimeter_ft: number
  width_m: number
  height_m: number
  pts_count: number
  is_sheet_border: boolean
  is_selected?: boolean
  score: number
  svg_path?: string
  svg_viewbox?: string
}

interface CandidateTableProps {
  candidates: Candidate[]
  selectedIdx: number
  onSelect: (idx: number) => void
  isPending: boolean
}

function CandidateTable({ candidates, selectedIdx, onSelect, isPending }: CandidateTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/60 text-xs text-muted-foreground">
            {['#', 'Area', 'ft²', 'W × H (m)', 'Perimeter', 'Type', 'Action'].map(h => (
              <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {candidates.map((c, i) => {
            const isSelected = i === selectedIdx
            return (
              <tr
                key={i}
                className={
                  isSelected
                    ? 'bg-green-50 font-semibold'
                    : c.is_sheet_border
                      ? 'opacity-50 bg-slate-50'
                      : 'hover:bg-muted/30 cursor-pointer'
                }
                onClick={() => !c.is_sheet_border && onSelect(i)}
              >
                <td className="px-3 py-2.5 whitespace-nowrap">
                  <span className="font-mono text-xs">{i + 1}</span>
                  {isSelected && (
                    <Badge className="ml-1.5 bg-green-600 text-white text-xs py-0">
                      ✓ Selected
                    </Badge>
                  )}
                  {!isSelected && i === 0 && !c.is_sheet_border && (
                    <Badge variant="outline" className="ml-1.5 text-xs py-0 border-green-400 text-green-700">
                      Recommended
                    </Badge>
                  )}
                </td>
                <td className="px-3 py-2.5 tabular-nums">{fmt(c.area_m2)} m²</td>
                <td className="px-3 py-2.5 tabular-nums text-muted-foreground">{fmt(c.area_ft2)}</td>
                <td className="px-3 py-2.5 tabular-nums">
                  {fmt(c.width_m)} × {fmt(c.height_m)}
                </td>
                <td className="px-3 py-2.5 tabular-nums">{fmt(c.perimeter_m)} m</td>
                <td className="px-3 py-2.5">
                  {c.is_sheet_border ? (
                    <Badge variant="destructive" className="text-xs">Sheet border</Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs text-green-700 border-green-300">
                      Building
                    </Badge>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {!c.is_sheet_border && !isSelected && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 text-xs px-2"
                      disabled={isPending}
                      onClick={e => { e.stopPropagation(); onSelect(i) }}
                    >
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

// ── Warning Alert ───────────────────────────────────────────────────────────────
function WarningAlert({ msg }: { msg: string }) {
  const isError = msg.startsWith('⚠') || /error|failed|cannot|no geometry|ole2frame/i.test(msg)
  const isOk    = /confirmed|applied|confirmed/i.test(msg)
  const cls = isOk
    ? 'bg-green-50 border-green-200 text-green-800'
    : isError
      ? 'bg-red-50 border-red-200 text-red-800'
      : 'bg-amber-50 border-amber-200 text-amber-800'
  const Icon = isOk ? CheckCircle2 : isError ? XCircle : AlertCircle
  return (
    <div className={`flex gap-2 rounded-lg p-3 text-sm border ${cls}`}>
      <Icon className="h-4 w-4 shrink-0 mt-0.5" />
      <span className="whitespace-pre-wrap">{msg}</span>
    </div>
  )
}

// ── Section toggle wrapper ──────────────────────────────────────────────────────
function Section({
  title, icon: Icon, badge, open, onToggle, children,
}: {
  title: string
  icon: any
  badge?: React.ReactNode
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader
        className="pb-2 cursor-pointer select-none"
        onClick={onToggle}
      >
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

// ── Main page ───────────────────────────────────────────────────────────────────
export default function DXFPage() {
  const fileRef = useRef<HTMLInputElement>(null)

  // Form state
  const [projectId,  setProjectId]  = useState('')
  const [units,      setUnits]      = useState('mm')
  const [applyMode,  setApplyMode]  = useState('false')
  const [file,       setFile]       = useState<File | null>(null)

  // Result state
  const [result,         setResult]        = useState<any>(null)
  const [selectedIdx,    setSelectedIdx]   = useState<number>(0)

  // UI toggles
  const [showDiag,        setShowDiag]       = useState(false)
  const [showCandidates,  setShowCandidates] = useState(true)
  const [showRooms,       setShowRooms]      = useState(false)
  const [showGuide,       setShowGuide]      = useState(false)

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: projects } = useQuery({
    queryKey: ['projects-list'],
    queryFn:  () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data ?? []),
  })

  const { data: guide } = useQuery({
    queryKey: ['dxf-guide'],
    queryFn:  () => api.get('/dxf/layers-guide').then(r => r.data),
  })

  // ── Upload mutation ────────────────────────────────────────────────────────
  const uploadMut = useMutation({
    mutationFn: async (overrideBoundary: number = -1) => {
      if (!file)      throw new Error('Select a DXF file first')
      if (!projectId) throw new Error('Select a project first')
      const fd = new FormData()
      fd.append('file',              file)
      fd.append('units',             units)
      fd.append('apply_to_building', applyMode)
      fd.append('selected_boundary', String(overrideBoundary))
      return api.post(`/dxf/upload/${projectId}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: ({ data }) => {
      setResult(data)
      // Auto-pick the first non-sheet-border candidate as selectedIdx
      const cands = data.extracted?.boundary_candidates ?? []
      const autoIdx = cands.findIndex((c: Candidate) => c.is_selected)
      setSelectedIdx(autoIdx >= 0 ? autoIdx : 0)
      toast.success('DXF parsed successfully')
    },
    onError: (e: any) =>
      toast.error(e.response?.data?.detail ?? e.message ?? 'Upload failed'),
  })

  // Re-parse with a different boundary selection
  const handleSelectBoundary = useCallback((idx: number) => {
    setSelectedIdx(idx)
    // If we already have a result, re-submit with the new boundary index
    if (result) {
      uploadMut.mutate(idx)
    }
  }, [result, uploadMut])

  // ── Derived state ──────────────────────────────────────────────────────────
  const ex         = result?.extracted
  const diag       = result?.diagnostics ?? {}
  const warnings   = result?.warnings     ?? []
  const candidates = (ex?.boundary_candidates ?? []) as Candidate[]
  const rooms      = (ex?.rooms ?? []) as any[]

  const hasArea     = ex && ex.building_footprint_area_m2 > 0
  const hasWalls    = ex && ex.total_wall_length_m > 0
  const hasExtWall  = ex && ex.external_wall_length_m > 0
  const hasIntWall  = ex && ex.internal_wall_length_m > 0
  const hasOLE      = (diag.ole2frame_count ?? 0) > 0
  const hasGeo      = (diag.geometric_entities ?? 0) > 0
  const hasLoops    = (diag.closed_loops_found ?? 0) > 0

  const svgViewbox  = ex?.svg_viewbox ?? '0 0 480 320'
  const unitsMatch  = result?.units_detected === result?.units_used
  const selBnd      = diag.selected_boundary ?? {}

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5 max-w-6xl mx-auto">

      {/* ── Upload card ─────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Upload className="h-5 w-5 text-primary" />
            Upload AutoCAD DXF Drawing
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Extracts out-to-out building footprint area, wall lengths, doors and windows
            directly from your AutoCAD DXF file.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Project */}
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Project <span className="text-destructive">*</span></Label>
              <Select onValueChange={setProjectId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select project…" />
                </SelectTrigger>
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
                  {[
                    { v: 'mm', label: 'Millimeters (mm)' },
                    { v: 'cm', label: 'Centimeters (cm)' },
                    { v: 'm',  label: 'Meters (m)' },
                    { v: 'ft', label: 'Feet (ft)' },
                    { v: 'in', label: 'Inches (in)' },
                  ].map(u => (
                    <SelectItem key={u.v} value={u.v}>{u.label}</SelectItem>
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
              if (f?.name.endsWith('.dxf')) setFile(f)
            }}
          >
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <div className="bg-primary/10 rounded-lg p-2">
                  <FileText className="h-8 w-8 text-primary" />
                </div>
                <div className="text-left">
                  <p className="font-semibold">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-2 h-5 text-xs text-destructive px-1"
                      onClick={e => { e.stopPropagation(); setFile(null); setResult(null) }}
                    >
                      Remove
                    </Button>
                  </p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
                <p className="text-sm font-medium">Drop DXF file here or click to browse</p>
                <p className="text-xs text-muted-foreground mt-1">
                  AutoCAD DXF format only · Max {settings_MAX_FILE_SIZE_MB} MB
                </p>
              </>
            )}
            <input
              ref={fileRef} type="file" accept=".dxf" className="hidden"
              onChange={e => { setFile(e.target.files?.[0] ?? null); setResult(null) }}
            />
          </div>

          <Button
            onClick={() => uploadMut.mutate(-1)}
            disabled={!file || !projectId || uploadMut.isPending}
            className="w-full h-11"
          >
            {uploadMut.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />Parsing DXF…</>
              : <><Upload className="h-4 w-4 mr-2" />Upload &amp; Parse DXF</>}
          </Button>
        </CardContent>
      </Card>

      {/* ── OLE / No-geometry error state ─────────────────────────────────── */}
      {ex && !hasArea && hasOLE && (
        <Card className="border-red-300 bg-red-50">
          <CardContent className="pt-5">
            <div className="flex gap-3">
              <XCircle className="h-6 w-6 text-red-500 shrink-0 mt-0.5" />
              <div className="space-y-2">
                <p className="font-semibold text-red-800">OLE Embedded Object Detected</p>
                <p className="text-sm text-red-700">
                  Your DXF contains an embedded OLE object (usually an AutoCAD drawing inserted as
                  an OLE link) but no directly accessible vector geometry. Area cannot be calculated.
                </p>
                <div className="bg-white border border-red-200 rounded-lg p-3 text-sm text-red-800 space-y-1">
                  <p className="font-medium">How to fix in AutoCAD:</p>
                  <ol className="list-decimal list-inside space-y-0.5 text-red-700">
                    <li>Open the DXF in AutoCAD</li>
                    <li>Type <code className="bg-red-100 px-1 rounded">EXPLODE</code> and press Enter</li>
                    <li>Select the OLE frame and press Enter</li>
                    <li>Go to <strong>File → Save As → AutoCAD 2010 DXF (ASCII)</strong></li>
                    <li>Re-upload the new file</li>
                  </ol>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Results ─────────────────────────────────────────────────────────── */}
      {ex && (
        <>
          {/* Units / scale info bar */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="outline" className="gap-1">
              <Ruler className="h-3 w-3" /> Selected: {(result.units_used ?? '').toUpperCase()}
            </Badge>
            <Badge
              variant={unitsMatch ? 'secondary' : 'destructive'}
              className="gap-1"
            >
              Auto-detected: {result.units_detected || 'unknown'}
              {!unitsMatch && ' ⚠'}
            </Badge>
            <Badge variant="outline">
              Scale: 1 DU = {result.scale_factor} m
            </Badge>
            {result.file_size_kb && (
              <Badge variant="outline">File: {result.file_size_kb} KB</Badge>
            )}
            {result.applied_to_building && (
              <Badge className="bg-green-600 text-white gap-1">
                <CheckCircle2 className="h-3 w-3" /> Applied to building
              </Badge>
            )}
          </div>

          {/* ── Primary result card — Building Footprint ───────────────────── */}
          <Card className={`${hasArea ? 'border-green-300' : 'border-orange-300'}`}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <SquareDashedBottom className="h-5 w-5 text-primary" />
                    Out-to-Out Building / Slab Area
                    {!hasArea && (
                      <Badge variant="destructive" className="ml-1">Not detected</Badge>
                    )}
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    External building boundary — primary value for slab, flooring, waterproofing BOQ
                  </p>
                </div>
                {hasArea && (
                  <Badge className="bg-green-100 text-green-800 border border-green-300">
                    ✓ Detected
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <KPI
                  label="Building Footprint"
                  value={hasArea ? fmtUnit(ex.building_footprint_area_m2, 'm²') : '0 m²'}
                  sub={hasArea ? fmtUnit(ex.building_footprint_area_ft2, 'ft²') : 'No boundary detected'}
                  colorClass={hasArea ? 'bg-green-50 border-green-200' : 'bg-orange-50 border-orange-200'}
                  large
                />
                <KPI
                  label="Slab Area (BOQ)"
                  value={hasArea ? fmtUnit(ex.slab_area_m2, 'm²') : '0 m²'}
                  sub="Used in BOQ calculations"
                  colorClass={hasArea ? 'bg-blue-50 border-blue-200' : ''}
                />
                <KPI
                  label="Boundary Perimeter"
                  value={hasArea ? fmtUnit(ex.boundary_perimeter_m, 'm') : '—'}
                  sub={hasArea ? fmtUnit(ex.boundary_perimeter_ft, 'ft') : ''}
                />
                <KPI
                  label="Footprint (ft²)"
                  value={hasArea ? fmtUnit(ex.building_footprint_area_ft2, 'ft²') : '—'}
                  sub={hasArea ? fmtUnit(ex.building_footprint_area_m2, 'm²') : ''}
                />
              </div>

              {/* Dimensions row */}
              {selBnd.width_m > 0 && selBnd.height_m > 0 && (
                <div className="flex items-center gap-3 text-sm bg-muted/40 rounded-lg px-4 py-2.5">
                  <span className="text-muted-foreground">Boundary dimensions:</span>
                  <span className="font-semibold">
                    {fmt(selBnd.width_m)} m × {fmt(selBnd.height_m)} m
                  </span>
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  <span className="text-muted-foreground">
                    {fmt(selBnd.width_m * 3.28084)} ft × {fmt(selBnd.height_m * 3.28084)} ft
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── SVG Boundary Preview ─────────────────────────────────────────── */}
          {candidates.length > 0 && (
            <SVGPreview
              candidates={candidates}
              selectedIdx={selectedIdx}
              viewbox={svgViewbox}
              onSelect={handleSelectBoundary}
            />
          )}

          {/* ── Boundary candidates selector ──────────────────────────────────── */}
          {candidates.length > 0 && (
            <Section
              title={`Boundary Candidates (${candidates.length})`}
              icon={Grid3X3}
              badge={
                candidates.length > 1 ? (
                  <Badge variant="secondary" className="text-xs">
                    Click a row to change selection
                  </Badge>
                ) : null
              }
              open={showCandidates}
              onToggle={() => setShowCandidates(s => !s)}
            >
              <p className="text-xs text-muted-foreground mb-3">
                Sorted by likelihood of being the building footprint. The first non-sheet-border
                boundary is auto-selected. Click any building boundary row or the{' '}
                <strong>Use this</strong> button to override.
              </p>
              <CandidateTable
                candidates={candidates}
                selectedIdx={selectedIdx}
                onSelect={handleSelectBoundary}
                isPending={uploadMut.isPending}
              />
              {uploadMut.isPending && (
                <div className="flex items-center gap-2 mt-3 text-sm text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Re-parsing with selected boundary…
                </div>
              )}
            </Section>
          )}

          {/* ── Walls + Openings ──────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Wall lengths */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Ruler className="h-4 w-4 text-primary" /> Wall Lengths
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">External walls</span>
                    <span className={`font-medium ${hasExtWall ? '' : 'text-muted-foreground'}`}>
                      {hasExtWall ? fmtUnit(ex.external_wall_length_m, 'm') : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Internal walls</span>
                    <span className={`font-medium ${hasIntWall ? '' : 'text-muted-foreground'}`}>
                      {hasIntWall ? fmtUnit(ex.internal_wall_length_m, 'm') : '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm font-semibold border-t pt-2">
                    <span>Total wall length</span>
                    <span>{hasWalls ? fmtUnit(ex.total_wall_length_m, 'm') : '—'}</span>
                  </div>
                </div>
                {!hasExtWall && !hasIntWall && hasWalls && (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded p-2">
                    Wall layers not classified — total shows all line geometry.
                    Add walls on <code>WALL</code>, <code>EXT_WALL</code>, or{' '}
                    <code>INT_WALL</code> layers for breakdown.
                  </p>
                )}
                {!hasWalls && (
                  <p className="text-xs text-muted-foreground">
                    No wall geometry detected. Place walls on named wall layers.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Doors & Windows */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <DoorOpen className="h-4 w-4 text-primary" /> Doors &amp; Windows
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <KPI
                    label="Doors"
                    value={String(ex.num_doors ?? 0)}
                    sub="Nos."
                    colorClass={ex.num_doors > 0 ? 'bg-blue-50 border-blue-200' : ''}
                  />
                  <KPI
                    label="Windows"
                    value={String(ex.num_windows ?? 0)}
                    sub="Nos."
                    colorClass={ex.num_windows > 0 ? 'bg-indigo-50 border-indigo-200' : ''}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Detected from INSERT blocks on DOOR / WINDOW layers.
                  Door/window count is independent of area calculation.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* ── Sub-areas (rooms) ─────────────────────────────────────────────── */}
          {rooms.length > 0 && (
            <Section
              title={`Detected Sub-Areas / Rooms (${rooms.length})`}
              icon={BarChart3}
              open={showRooms}
              onToggle={() => setShowRooms(s => !s)}
            >
              <p className="text-xs text-muted-foreground mb-3">
                Closed boundaries smaller than the building footprint, likely individual rooms or
                zones. These are secondary — the primary BOQ area is the out-to-out footprint above.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                {rooms.map((r: any, i: number) => (
                  <div
                    key={i}
                    className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs"
                  >
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

          {/* ── Diagnostics panel ─────────────────────────────────────────────── */}
          <Section
            title="DXF Diagnostics"
            icon={Info}
            badge={
              <Badge
                variant={hasGeo ? 'secondary' : 'destructive'}
                className="text-xs"
              >
                {diag.segments_extracted ?? 0} segments
              </Badge>
            }
            open={showDiag}
            onToggle={() => setShowDiag(s => !s)}
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {/* Entity counts */}
              <div>
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-2">
                  Entity Counts
                </p>
                <DiagRow label="Total entities"      value={diag.total_entities ?? 0} />
                <DiagRow label="Geometric entities"  value={diag.geometric_entities ?? 0} />
                <DiagRow label="LINE"                value={diag.line_count ?? 0} />
                <DiagRow label="LWPOLYLINE"          value={diag.lwpolyline_count ?? 0} />
                <DiagRow label="POLYLINE"            value={diag.polyline_count ?? 0} />
                <DiagRow label="ARC"                 value={diag.arc_count ?? 0} />
                <DiagRow label="CIRCLE"              value={diag.circle_count ?? 0} />
                <DiagRow label="SPLINE"              value={diag.spline_count ?? 0} />
                <DiagRow label="ELLIPSE"             value={diag.ellipse_count ?? 0} />
                <DiagRow label="HATCH"               value={diag.hatch_count ?? 0} />
                <DiagRow label="INSERT (blocks)"     value={diag.insert_count ?? 0} />
                <DiagRow
                  label="OLE2FRAME"
                  value={diag.ole2frame_count ?? 0}
                />
              </div>

              {/* Geometry analysis */}
              <div>
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-2">
                  Geometry Analysis
                </p>
                <DiagRow label="Segments extracted"      value={diag.segments_extracted ?? 0} />
                <DiagRow label="Closed loops found"      value={diag.closed_loops_found ?? 0} />
                <DiagRow label="Boundary candidates"     value={diag.boundary_candidates_count ?? 0} />
                <DiagRow label="Snap tolerance (DU)"     value={diag.snap_tolerance_drawing_units ?? '—'} />
                <DiagRow label="$INSUNITS value"         value={diag.insunits_value ?? 0} />
                <DiagRow label="Scale factor (m/DU)"     value={diag.scale_factor_m_per_du ?? '—'} />
                {diag.drawing_extents && (
                  <>
                    <DiagRow
                      label="Drawing width (DU)"
                      value={diag.drawing_extents.width_drawing_units}
                    />
                    <DiagRow
                      label="Drawing height (DU)"
                      value={diag.drawing_extents.height_drawing_units}
                    />
                    <DiagRow
                      label="Drawing width (m)"
                      value={diag.drawing_extents.width_m}
                    />
                    <DiagRow
                      label="Drawing height (m)"
                      value={diag.drawing_extents.height_m}
                    />
                  </>
                )}
              </div>

              {/* Selected boundary */}
              <div>
                <p className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-2">
                  Selected Boundary
                </p>
                {selBnd.area_m2 != null ? (
                  <>
                    <DiagRow label="Area (m²)"      value={selBnd.area_m2} />
                    <DiagRow label="Area (ft²)"     value={selBnd.area_ft2} />
                    <DiagRow label="Perimeter (m)"  value={selBnd.perimeter_m} />
                    <DiagRow label="Width (m)"      value={selBnd.width_m} />
                    <DiagRow label="Height (m)"     value={selBnd.height_m} />
                    <DiagRow label="Vertices"       value={selBnd.pts_count ?? '—'} />
                    <DiagRow label="Score"          value={
                      typeof selBnd.score === 'number' ? selBnd.score.toFixed(1) : '—'
                    } />
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">No boundary selected</p>
                )}
              </div>
            </div>
          </Section>

          {/* ── Warnings list ─────────────────────────────────────────────────── */}
          {warnings.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Parser Messages
              </p>
              {warnings.map((w: string, i: number) => (
                <WarningAlert key={i} msg={w} />
              ))}
            </div>
          )}

          {/* ── Applied confirmation banner ────────────────────────────────────── */}
          {result.applied_to_building && (
            <div className="flex gap-3 bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-700">
              <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Building dimensions updated successfully.</p>
                <p className="text-green-600 mt-0.5">
                  Slab area, wall lengths, and opening counts have been written to the building.
                  Go to <strong>Estimation</strong> and run the calculation to generate BOQ quantities.
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Layer guide ───────────────────────────────────────────────────────── */}
      <Section
        title="DXF Layer Naming Guide"
        icon={Layers}
        open={showGuide}
        onToggle={() => setShowGuide(s => !s)}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
          {guide &&
            Object.entries(guide)
              .filter(([k]) => k.endsWith('_layers'))
              .map(([key, vals]: any) => (
                <div key={key}>
                  <p className="font-semibold capitalize mb-1.5 text-xs">
                    {key.replace('_layers', '').replace(/_/g, ' ')} layers
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {vals.map((v: string) => (
                      <Badge key={v} variant="outline" className="text-xs font-mono">
                        {v}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
        </div>
        {guide?.tips && (
          <ul className="mt-5 space-y-2">
            {guide.tips.map((t: string, i: number) => (
              <li key={i} className="text-xs text-muted-foreground flex gap-2">
                <span className="text-primary shrink-0 font-bold">•</span>
                {t}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}

// Read max file size from Vite env (falls back to 50 MB)
const settings_MAX_FILE_SIZE_MB: number =
  Number(import.meta.env?.VITE_MAX_FILE_SIZE_MB ?? 50) || 50
