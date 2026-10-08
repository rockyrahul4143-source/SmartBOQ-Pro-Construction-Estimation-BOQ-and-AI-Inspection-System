/**
 * ManualColumnBBS.tsx
 * Complete member-specific Manual Column BBS UI.
 *
 * Sections:
 *  1. Column Information
 *  2. Main Vertical Bars (multiple groups)
 *  3. Level-wise / Reduction Reinforcement
 *  4. Master / Main Closed Stirrup
 *  5. Short Link
 *  6. Long Link
 *  7. Cross Tie
 *  8. Column Zones
 *  — Calculate Complete Column BBS —
 *  9. Unified BBS Results table + Calculation Trace
 * 10. Export (Excel / PDF)
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Plus, Trash2, Calculator, Info, ChevronDown, ChevronUp,
  Download, FileText, CheckCircle2,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

/* ── options ─────────────────────────────────────────── */
const CONCRETE_GRADES     = ['M15','M20','M25','M30','M35','M40','M45','M50']
const STEEL_GRADES        = ['FE415','FE500','FE550','FE600']
const BAR_DIAS            = [8,10,12,16,20,25,28,32,36,40]
const LAP_METHODS         = ['30D','40D','45D','50D','60D','DRAWING_SPECIFIED','CODE_BASED','CUSTOM']
const LAP_CONDITIONS      = ['TENSION','COMPRESSION']
const HOOK_TYPES          = ['90_DEGREE','135_DEGREE','180_DEGREE','45_DEGREE','STANDARD_HOOK','CUSTOM']
const LINK_SHAPES         = ['RECTANGULAR','SQUARE']
const DIM_CONVENTIONS     = ['INSIDE','CENTERLINE','OUTSIDE','DRAWING_SPECIFIED']
const ZONE_TYPES          = ['CONFINED','REGULAR','LAP_SPLICE','CUSTOM']
const ENDPOINT_CONVS      = ['BOTH_ENDS_INCLUDED','ONE_END','NO_ENDS','DRAWING_SPECIFIED']

/* ── helpers ─────────────────────────────────────────── */
const unitWt = (d: number) => (d * d / 162).toFixed(3)
function lapPreview(method: string, dia: number) {
  const map: Record<string, number> = { '30D':30,'40D':40,'45D':45,'50D':50,'60D':60 }
  if (map[method]) return `${map[method]} × ${dia} = ${map[method]*dia} mm`
  return null
}

/* ── cutting length preview for a rectangular link ───── */
function linkCLPreview(colW:number, colD:number, cover:number, dia:number,
  convention: string, hookExt:number, hookType:string) {
  if (!colW || !colD) return null
  let iw=0, id=0
  if (convention==='INSIDE') {
    iw = colW - 2*cover - dia
    id = colD - 2*cover - dia
  } else if (convention==='CENTERLINE') {
    iw = colW - 2*cover
    id = colD - 2*cover
  } else if (convention==='OUTSIDE') {
    iw = colW; id = colD
  } else return null
  const hook_allow = hookType==='NONE' ? 0 : hookExt * 2
  const bend_ded   = hookType==='STANDARD_135' ? 3*dia : (hookType==='STANDARD_90' ? 2*dia : 0)
  const cl = 2*iw + 2*id + hook_allow - bend_ded
  return { iw, id, hook_allow, bend_ded, cl }
}

interface Props { projectId: string; sheetId: string; sheet: any }

/* ── empty defaults ──────────────────────────────────── */
const EMPTY_MAIN_BAR = {
  bar_mark:'', description:'', diameter:20, number_of_bars:8, number_of_units:1,
  lap_method:'CODE_BASED', lap_length:'', lap_condition:'COMPRESSION',
  development_length:null, top_anchorage:null, bottom_anchorage:null,
  starter_bar:false, hook_type:null as string|null, hook_extension:0, remarks:''
}
const EMPTY_REDUCTION = {
  level_name:'', start_height:'', end_height:'',
  bars_to_reduce:'', reduction_percentage:0, new_bar_configuration:'', remarks:''
}
const EMPTY_LINK = {
  link_mark:'', description:'', diameter:8, shape:'RECTANGULAR',
  spacing:'', zone_name:'', zone_length:'',
  link_width:'', link_depth:'',
  number_of_legs:4, hook_type:'90_DEGREE', hook_extension:0,
  bend_angle:90, dimension_convention:'INSIDE',
  endpoint_convention:'BOTH_ENDS_INCLUDED', remarks:''
}
const EMPTY_CROSS_TIE = {
  tie_mark:'', description:'', diameter:8,
  spacing:'', zone_name:'', zone_length:'',
  tie_length:'', hook_type:'135_DEGREE', hook_extension:75,
  bend_angle:135, endpoint_convention:'BOTH_ENDS_INCLUDED', remarks:''
}
const EMPTY_ZONE = {
  zone_name:'', zone_type:'REGULAR', start_height:'',
  end_height:'', link_mark:'', spacing:'', remarks:''
}

export default function ManualColumnBBS({ projectId, sheetId, sheet }: Props) {

  /* ── column info ─────────────────────────── */
  const [info, setInfo] = useState({
    column_mark:'',
    number_of_units:1, column_width:'', column_depth:'', clear_floor_height:'',
    concrete_grade:'M25', steel_grade:'FE415', cover:40,
  })

  /* ── reinforcement groups ────────────────── */
  const [mainBars,       setMainBars]       = useState<any[]>([])
  const [reductions,     setReductions]     = useState<any[]>([])
  const [masterStirrups, setMasterStirrups] = useState<any[]>([])
  const [shortLinks,     setShortLinks]     = useState<any[]>([])
  const [longLinks,      setLongLinks]      = useState<any[]>([])
  const [crossTies,      setCrossTies]      = useState<any[]>([])
  const [zones,          setZones]          = useState<any[]>([])

  /* ── add-form visibility ─────────────────── */
  const [showAddMainBar,    setShowAddMainBar]    = useState(false)
  const [showAddReduction,  setShowAddReduction]  = useState(false)
  const [showAddMaster,     setShowAddMaster]     = useState(false)
  const [showAddShort,      setShowAddShort]      = useState(false)
  const [showAddLong,       setShowAddLong]       = useState(false)
  const [showAddCrossTie,   setShowAddCrossTie]   = useState(false)
  const [showAddZone,       setShowAddZone]       = useState(false)

  /* ── add-form values ─────────────────────── */
  const [mainBarForm,    setMainBarForm]    = useState<any>({...EMPTY_MAIN_BAR})
  const [reductionForm,  setReductionForm]  = useState<any>({...EMPTY_REDUCTION})
  const [masterForm,     setMasterForm]     = useState<any>({...EMPTY_LINK, link_mark:'', number_of_legs:4})
  const [shortForm,      setShortForm]      = useState<any>({...EMPTY_LINK, link_mark:'', number_of_legs:2})
  const [longForm,       setLongForm]       = useState<any>({...EMPTY_LINK, link_mark:'', number_of_legs:2})
  const [crossTieForm,   setCrossTieForm]   = useState<any>({...EMPTY_CROSS_TIE})
  const [zoneForm,       setZoneForm]       = useState<any>({...EMPTY_ZONE})

  /* ── section collapse ────────────────────── */
  const [open, setOpen] = useState<Record<string,boolean>>({
    info:true, mainBars:false, reductions:false, master:false,
    short:false, long:false, cross:false, zones:false
  })
  const toggle = (k: string) => setOpen(o=>({...o,[k]:!o[k]}))

  /* ── result & trace ──────────────────────── */
  const [result, setResult] = useState<any>(null)
  const [showTrace, setShowTrace] = useState<Record<number,boolean>>({})

  /* ── calc mutation ───────────────────────── */
  const calcMut = useMutation({
    mutationFn: (d: any) => api.post('/bbs/complete/column', d),
    onSuccess: ({ data }) => { 
      // Validate response structure before setting
      if (!data) {
        toast.error('Invalid response: no data returned');
        return;
      }
      
      // Ensure arrays exist
      if (data.unified_bbs_entries && !Array.isArray(data.unified_bbs_entries)) {
        console.error('unified_bbs_entries is not an array:', data.unified_bbs_entries);
        toast.error('Invalid response structure: unified_bbs_entries must be an array');
        return;
      }
      
      if (data.diameter_summary && !Array.isArray(data.diameter_summary)) {
        console.error('diameter_summary is not an array:', data.diameter_summary);
        toast.error('Invalid response structure: diameter_summary must be an array');
        return;
      }
      
      setResult(data); 
      toast.success('Column BBS calculated!');
    },
    onError: (e: any) => {
      console.error('Column BBS calculation error:', e);
      const errorMsg = e.response?.data?.detail ?? e.message ?? 'Calculation failed';
      toast.error(errorMsg);
    },
  })

  const handleCalculate = () => {
    if (!info.column_mark)       { toast.error('Column Mark is required');       return }
    if (!info.column_width)      { toast.error('Column Width is required');      return }
    if (!info.column_depth)      { toast.error('Column Depth is required');      return }
    if (!info.clear_floor_height){ toast.error('Clear Floor Height is required');return }

    // Enrich master stirrups with column dimensions (required by backend model)
    const enrichedMasterStirrups = masterStirrups.map(s => ({
      ...s,
      column_width: Number(info.column_width),
      column_depth: Number(info.column_depth),
      cover: Number(info.cover),
      spacing: Number(s.spacing) || 0,
      zone_length: Number(s.zone_length) || 0,
      hook_type: s.hook_type || '90_DEGREE',
    }))

    // Enrich short/long links — ensure link_width and link_depth
    const enrichLink = (links: any[]) => links.map(l => ({
      ...l,
      link_width: Number(l.link_width) || (Number(info.column_width) - 2*Number(info.cover) - l.diameter),
      link_depth: Number(l.link_depth) || (Number(info.column_depth) - 2*Number(info.cover) - l.diameter),
      cover: Number(info.cover),
      spacing: Number(l.spacing) || 0,
      zone_length: Number(l.zone_length) || 0,
      hook_type: l.hook_type || '90_DEGREE',
    }))

    const enrichedCrossTies = crossTies.map(t => ({
      ...t,
      tie_length: Number(t.tie_length) || (Number(info.column_width) - 2*Number(info.cover)),
      spacing: Number(t.spacing) || 0,
      zone_length: Number(t.zone_length) || 0,
      hook_type: t.hook_type || '135_DEGREE',
    }))

    // Fix main bars — null out empty anchorages
    const enrichedMainBars = mainBars.map(b => ({
      ...b,
      development_length: b.development_length || null,
      top_anchorage: b.top_anchorage || null,
      bottom_anchorage: b.bottom_anchorage || null,
      lap_length: b.lap_length || null,
      hook_type: b.hook_type || null,
    }))

    calcMut.mutate({
      ...info,
      project: projectId,
      column_width: Number(info.column_width),
      column_depth: Number(info.column_depth),
      clear_floor_height: Number(info.clear_floor_height),
      cover: Number(info.cover),
      number_of_units: Number(info.number_of_units),
      main_vertical_bars: enrichedMainBars,
      reduction_levels:   reductions,
      master_stirrups:    enrichedMasterStirrups,
      short_links:        enrichLink(shortLinks),
      long_links:         enrichLink(longLinks),
      cross_ties:         enrichedCrossTies,
      column_zones:       zones,
    })
  }

  /* ── render helpers ──────────────────────── */
  const inp = (label: string, val: any, set: (v:any)=>void, type='text', step='1') => (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input type={type} step={step} value={val??''} className="h-8 text-sm"
        onChange={e=>set(type==='number'
          ? (e.target.value==='' ? '' : Number(e.target.value))
          : e.target.value)}/>
    </div>
  )
  const sel = (label: string, val: any, set: (v:any)=>void, opts: string[]) => (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Select value={String(val)} onValueChange={set}>
        <SelectTrigger className="h-8 text-sm"><SelectValue/></SelectTrigger>
        <SelectContent>{opts.map(o=><SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  )

  /* ── link form (used for master, short, long) ────────── */
  function LinkForm({ form, setForm, onAdd, onCancel, label }: any) {
    const preview = linkCLPreview(
      Number(info.column_width), Number(info.column_depth), Number(info.cover),
      form.diameter, form.dimension_convention, Number(form.hook_extension), form.hook_type
    )
    const sp = Number(form.spacing)||0, zl = Number(form.zone_length)||0
    const n_prev = sp>0 && zl>0 ? Math.floor(zl/sp)+1 : null
    return (
      <Card className="mt-3 border-green-200">
        <CardContent className="p-3 space-y-3">
          <p className="text-xs font-semibold text-green-900">{label}</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {inp('Link Mark *',          form.link_mark,           v=>setForm({...form,link_mark:v}))}
            {inp('Description',          form.description,         v=>setForm({...form,description:v}))}
            {sel('Diameter (mm)',         String(form.diameter),    v=>setForm({...form,diameter:Number(v)}), BAR_DIAS.map(String))}
            {sel('Shape',                form.shape,               v=>setForm({...form,shape:v}), LINK_SHAPES)}
            {inp('Spacing (mm)',         form.spacing,             v=>setForm({...form,spacing:v}), 'number','1')}
            {inp('Zone Name',            form.zone_name,           v=>setForm({...form,zone_name:v}))}
            {inp('Zone Length (mm)',      form.zone_length,         v=>setForm({...form,zone_length:v}), 'number','1')}
            {inp('No. of Legs',          form.number_of_legs,      v=>setForm({...form,number_of_legs:v}), 'number','1')}
            {inp('Link Width (mm)',       form.link_width,          v=>setForm({...form,link_width:v}), 'number','1')}
            {inp('Link Depth (mm)',       form.link_depth,          v=>setForm({...form,link_depth:v}), 'number','1')}
            {sel('Hook Type',            form.hook_type,           v=>setForm({...form,hook_type:v}), HOOK_TYPES)}
            {inp('Hook Extension (mm)',   form.hook_extension,      v=>setForm({...form,hook_extension:v}), 'number','1')}
            {inp('Bend Angle',           form.bend_angle,          v=>setForm({...form,bend_angle:v}), 'number','1')}
            {sel('Dimension Convention', form.dimension_convention,v=>setForm({...form,dimension_convention:v}), DIM_CONVENTIONS)}
            {sel('Endpoint Convention',  form.endpoint_convention, v=>setForm({...form,endpoint_convention:v}), ENDPOINT_CONVS)}
            {inp('Remarks',              form.remarks,             v=>setForm({...form,remarks:v}))}
          </div>
          {/* Live cutting length preview */}
          {preview && (
            <div className="p-2 bg-green-50 rounded text-xs space-y-0.5">
              <p className="font-semibold text-green-800">Cutting Length Preview ({form.dimension_convention}):</p>
              <p>Inner Width  = <strong>{preview.iw} mm</strong></p>
              <p>Inner Depth  = <strong>{preview.id} mm</strong></p>
              <p>CL = 2×{preview.iw} + 2×{preview.id} + {preview.hook_allow}(hooks) − {preview.bend_ded}(bends) = <strong>{preview.cl.toFixed(0)} mm</strong></p>
              <p>Unit Wt = {form.diameter}²/162 = <strong>{unitWt(form.diameter)} kg/m</strong></p>
              {n_prev !== null && <p>No. of Links (L/s+1) = {zl}/{sp}+1 = <strong>{n_prev}</strong></p>}
            </div>
          )}
          {lapPreview(form.lap_method, form.diameter) && (
            <p className="text-xs text-blue-700">
              Lap: {lapPreview(form.lap_method, form.diameter)}
            </p>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={onAdd}>Add</Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  /* ── cross tie form ──────────────────────── */
  function CrossTieFormComp({ form, setForm, onAdd, onCancel }: any) {
    const sp = Number(form.spacing)||0, zl = Number(form.zone_length)||0
    const n_prev = sp>0 && zl>0 ? Math.floor(zl/sp)+1 : null
    return (
      <Card className="mt-3 border-red-200">
        <CardContent className="p-3 space-y-3">
          <p className="text-xs font-semibold text-red-900">Cross Tie</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {inp('Tie Mark *',          form.tie_mark,         v=>setForm({...form,tie_mark:v}))}
            {inp('Description',         form.description,      v=>setForm({...form,description:v}))}
            {sel('Diameter (mm)',        String(form.diameter), v=>setForm({...form,diameter:Number(v)}), BAR_DIAS.map(String))}
            {inp('Spacing (mm)',        form.spacing,          v=>setForm({...form,spacing:v}), 'number','1')}
            {inp('Zone Name',           form.zone_name,        v=>setForm({...form,zone_name:v}))}
            {inp('Zone Length (mm)',     form.zone_length,      v=>setForm({...form,zone_length:v}), 'number','1')}
            {inp('Tie Length (mm)',      form.tie_length,       v=>setForm({...form,tie_length:v}), 'number','1')}
            {sel('Hook Type',           form.hook_type,        v=>setForm({...form,hook_type:v}), HOOK_TYPES)}
            {inp('Hook Extension (mm)', form.hook_extension,   v=>setForm({...form,hook_extension:v}), 'number','1')}
            {inp('Bend Angle',          form.bend_angle,       v=>setForm({...form,bend_angle:v}), 'number','1')}
            {sel('Endpoint Convention', form.endpoint_convention,v=>setForm({...form,endpoint_convention:v}), ENDPOINT_CONVS)}
            {inp('Remarks',             form.remarks,          v=>setForm({...form,remarks:v}))}
          </div>
          {n_prev !== null && (
            <p className="text-xs text-muted-foreground">
              No. of Cross Ties (L/s+1) = {zl}/{sp}+1 = <strong>{n_prev}</strong>
            </p>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={onAdd}>Add Cross Tie</Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  /* ── generic item list ───────────────────── */
  function ItemList({ items, labelFn, onRemove }: { items:any[], labelFn:(b:any)=>string, onRemove:(i:number)=>void }) {
    if (!items.length) return null
    return (
      <div className="space-y-1.5 mb-2">
        {items.map((b,i)=>(
          <div key={i} className="flex items-center justify-between px-3 py-2 bg-muted/30 rounded border text-sm">
            <span dangerouslySetInnerHTML={{ __html: labelFn(b) }}/>
            <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive" onClick={()=>onRemove(i)}>
              <Trash2 className="h-3 w-3"/>
            </Button>
          </div>
        ))}
      </div>
    )
  }

  /* ── section header ──────────────────────── */
  const SH = ({ step, title, badge, keyName }: any) => (
    <CardHeader className="pb-2 cursor-pointer select-none" onClick={()=>toggle(keyName)}>
      <div className="flex items-center justify-between">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="bg-primary text-white rounded-full w-6 h-6 flex items-center justify-center text-xs shrink-0">{step}</span>
          {title}
          {badge!==undefined && <Badge variant="outline">{badge}</Badge>}
        </CardTitle>
        {open[keyName] ? <ChevronUp className="h-4 w-4 shrink-0"/> : <ChevronDown className="h-4 w-4 shrink-0"/>}
      </div>
    </CardHeader>
  )

  return (
    <div className="space-y-4">

      {/* workflow guide */}
      <Card className="border-purple-200 bg-purple-50/40">
        <CardContent className="p-3 flex gap-2">
          <Info className="h-4 w-4 text-purple-600 mt-0.5 shrink-0"/>
          <p className="text-xs text-purple-900">
            <strong>Column BBS Workflow:</strong> Column Info → Main Vertical Bars (multiple groups) → 
            Level-wise Reductions → Master Stirrup → Short Link → Long Link → Cross Tie → Zones → Calculate.
            Cutting lengths are derived from column dimensions, cover, and hook geometry. No hardcoded values.
          </p>
        </CardContent>
      </Card>

      {/* ═══ 1. COLUMN INFORMATION ═════════════════════════ */}
      <Card>
        <SH step="1" title="Column Information" keyName="info"/>
        {open.info && (
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {inp('Column Mark *',           info.column_mark,        v=>setInfo({...info,column_mark:v}))}
              {inp('No. of Units',            info.number_of_units,    v=>setInfo({...info,number_of_units:v}), 'number','1')}
              {inp('Column Width (mm) *',     info.column_width,       v=>setInfo({...info,column_width:v}), 'number','1')}
              {inp('Column Depth (mm) *',     info.column_depth,       v=>setInfo({...info,column_depth:v}), 'number','1')}
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Column Size</Label>
                <div className="h-8 flex items-center px-3 rounded border bg-muted/40 text-sm font-mono text-muted-foreground">
                  {info.column_width && info.column_depth ? `${info.column_width} × ${info.column_depth} mm` : '— × — mm'}
                </div>
              </div>
              {inp('Clear Floor Height (mm) *', info.clear_floor_height, v=>setInfo({...info,clear_floor_height:v}), 'number','1')}
              {sel('Concrete Grade',          info.concrete_grade,     v=>setInfo({...info,concrete_grade:v}), CONCRETE_GRADES)}
              {sel('Steel Grade',             info.steel_grade,        v=>setInfo({...info,steel_grade:v}), STEEL_GRADES)}
              {inp('Clear Cover (mm)',         info.cover,              v=>setInfo({...info,cover:v}), 'number','1')}
            </div>
          </CardContent>
        )}
      </Card>

      {/* ═══ 2. MAIN VERTICAL BARS ═════════════════════════ */}
      <Card>
        <SH step="2" title="Main Vertical Bars" badge={`${mainBars.length} groups`} keyName="mainBars"/>
        {open.mainBars && (
          <CardContent>
            <div className="mb-3 p-3 bg-blue-50 rounded border border-blue-200 text-xs text-blue-900">
              <strong>Multiple groups allowed.</strong> Example: Group 1 = 8×Ø20 (mark M1), Group 2 = 4×Ø16 (mark M2).
              Each group has independent lap, anchorage and hook settings.
            </div>
            <ItemList items={mainBars}
              labelFn={b=>`<strong>${b.bar_mark}</strong> &nbsp; ${b.number_of_bars} × Ø${b.diameter}mm &nbsp; <span class='text-xs text-gray-500'>${b.lap_method} / ${b.lap_condition}${lapPreview(b.lap_method,b.diameter) ? ` → ${lapPreview(b.lap_method,b.diameter)}` : ''}</span>`}
              onRemove={i=>setMainBars(mainBars.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddMainBar(!showAddMainBar)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Main Bar Group
            </Button>
            {showAddMainBar && (
              <Card className="mt-3 border-blue-200">
                <CardContent className="p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inp('Bar Mark *',           mainBarForm.bar_mark,        v=>setMainBarForm({...mainBarForm,bar_mark:v}))}
                    {inp('Description',          mainBarForm.description,     v=>setMainBarForm({...mainBarForm,description:v}))}
                    {sel('Diameter (mm) *',      String(mainBarForm.diameter),v=>setMainBarForm({...mainBarForm,diameter:Number(v)}), BAR_DIAS.map(String))}
                    {inp('No. of Bars / Column *',mainBarForm.number_of_bars, v=>setMainBarForm({...mainBarForm,number_of_bars:v}), 'number','1')}
                    {inp('No. of Units',         mainBarForm.number_of_units, v=>setMainBarForm({...mainBarForm,number_of_units:v}), 'number','1')}
                    {sel('Lap Method',           mainBarForm.lap_method,      v=>setMainBarForm({...mainBarForm,lap_method:v}), LAP_METHODS)}
                    {['DRAWING_SPECIFIED','CUSTOM'].includes(mainBarForm.lap_method) &&
                      inp('Lap Length (mm)',     mainBarForm.lap_length,      v=>setMainBarForm({...mainBarForm,lap_length:v}), 'number','1')}
                    {sel('Lap Condition',        mainBarForm.lap_condition,   v=>setMainBarForm({...mainBarForm,lap_condition:v}), LAP_CONDITIONS)}
                    {inp('Development Length (mm)', mainBarForm.development_length, v=>setMainBarForm({...mainBarForm,development_length:v}), 'number','1')}
                    {inp('Top Anchorage (mm)',   mainBarForm.top_anchorage,   v=>setMainBarForm({...mainBarForm,top_anchorage:v}), 'number','1')}
                    {inp('Bottom Anchorage (mm)',mainBarForm.bottom_anchorage,v=>setMainBarForm({...mainBarForm,bottom_anchorage:v}), 'number','1')}
                    {sel('Hook Type',            mainBarForm.hook_type||'— No Hook —',       v=>setMainBarForm({...mainBarForm,hook_type:v==='— No Hook —'?null:v}), ['— No Hook —',...HOOK_TYPES])}
                    {mainBarForm.hook_type!=='NONE' &&
                      inp('Hook Extension (mm)', mainBarForm.hook_extension,  v=>setMainBarForm({...mainBarForm,hook_extension:v}), 'number','1')}
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Starter Bar</Label>
                      <Select value={mainBarForm.starter_bar?'yes':'no'} onValueChange={v=>setMainBarForm({...mainBarForm,starter_bar:v==='yes'})}>
                        <SelectTrigger className="h-8 text-sm"><SelectValue/></SelectTrigger>
                        <SelectContent><SelectItem value="yes">Yes</SelectItem><SelectItem value="no">No</SelectItem></SelectContent>
                      </Select>
                    </div>
                    {inp('Remarks', mainBarForm.remarks, v=>setMainBarForm({...mainBarForm,remarks:v}))}
                  </div>
                  {/* live previews */}
                  {lapPreview(mainBarForm.lap_method, mainBarForm.diameter) && (
                    <p className="text-xs text-blue-700 bg-blue-50 px-2 py-1 rounded">
                      Lap: {lapPreview(mainBarForm.lap_method, mainBarForm.diameter)}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Unit Weight: {mainBarForm.diameter}²/162 = <strong>{unitWt(mainBarForm.diameter)} kg/m</strong>
                  </p>
                  {info.clear_floor_height && (
                    <p className="text-xs text-muted-foreground">
                      Base cutting length = clear height {info.clear_floor_height} mm + top anchor + bottom anchor + lap
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button size="sm" onClick={()=>{
                      if(!mainBarForm.bar_mark){toast.error('Bar Mark required');return}
                      setMainBars([...mainBars,{...mainBarForm}])
                      setMainBarForm({...EMPTY_MAIN_BAR}); setShowAddMainBar(false)
                      toast.success('Main bar group added')
                    }}>Add Group</Button>
                    <Button size="sm" variant="ghost" onClick={()=>setShowAddMainBar(false)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 3. LEVEL-WISE REDUCTION ═══════════════════════ */}
      <Card>
        <SH step="3" title="Level-wise Reinforcement Reduction" badge={`${reductions.length} levels`} keyName="reductions"/>
        {open.reductions && (
          <CardContent>
            <div className="mb-3 p-3 bg-amber-50 rounded border border-amber-200 text-xs text-amber-900">
              <strong>Optional.</strong> Use when main bar count or diameter changes at different floor levels.
              Example: GF→1F: 8×Ø20, 1F→2F: 6×Ø20+2×Ø16, etc. Enter bar marks to be reduced and percentage.
            </div>
            <ItemList items={reductions}
              labelFn={b=>`<strong>${b.level_name}</strong> &nbsp; Reduce: ${b.bars_to_reduce} &nbsp; <span class='text-xs text-gray-500'>${b.reduction_percentage}%</span>`}
              onRemove={i=>setReductions(reductions.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddReduction(!showAddReduction)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Reduction Level
            </Button>
            {showAddReduction && (
              <Card className="mt-3 border-amber-200">
                <CardContent className="p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inp('Level Name *',           reductionForm.level_name,            v=>setReductionForm({...reductionForm,level_name:v}))}
                    {inp('Start Height (mm)',       reductionForm.start_height,          v=>setReductionForm({...reductionForm,start_height:v}), 'number','1')}
                    {inp('End Height (mm)',         reductionForm.end_height,            v=>setReductionForm({...reductionForm,end_height:v}), 'number','1')}
                    {inp('Bars to Reduce (marks)',  reductionForm.bars_to_reduce,        v=>setReductionForm({...reductionForm,bars_to_reduce:v}))}
                    {inp('Reduction %',             reductionForm.reduction_percentage,  v=>setReductionForm({...reductionForm,reduction_percentage:v}), 'number','1')}
                    {inp('New Bar Configuration',   reductionForm.new_bar_configuration, v=>setReductionForm({...reductionForm,new_bar_configuration:v}))}
                    {inp('Remarks',                 reductionForm.remarks,               v=>setReductionForm({...reductionForm,remarks:v}))}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={()=>{
                      if(!reductionForm.level_name){toast.error('Level Name required');return}
                      setReductions([...reductions,{...reductionForm}])
                      setReductionForm({...EMPTY_REDUCTION}); setShowAddReduction(false)
                      toast.success('Reduction level added')
                    }}>Add Level</Button>
                    <Button size="sm" variant="ghost" onClick={()=>setShowAddReduction(false)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 4. MASTER STIRRUP ═════════════════════════════ */}
      <Card>
        <SH step="4" title="Master / Main Closed Stirrup" badge={`${masterStirrups.length}`} keyName="master"/>
        {open.master && (
          <CardContent>
            <ItemList items={masterStirrups}
              labelFn={b=>`<strong>${b.link_mark}</strong> &nbsp; Ø${b.diameter}mm @ ${b.spacing}mm &nbsp; <span class='text-xs text-gray-500'>${b.zone_name||'full height'} / ${b.dimension_convention}</span>`}
              onRemove={i=>setMasterStirrups(masterStirrups.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddMaster(!showAddMaster)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Master Stirrup
            </Button>
            {showAddMaster && (
              <LinkForm form={masterForm} setForm={setMasterForm} label="Master / Main Closed Stirrup"
                onAdd={()=>{
                  if(!masterForm.link_mark){toast.error('Link Mark required');return}
                  setMasterStirrups([...masterStirrups,{...masterForm}])
                  setMasterForm({...EMPTY_LINK,link_mark:'',number_of_legs:4}); setShowAddMaster(false)
                  toast.success('Master stirrup added')
                }}
                onCancel={()=>setShowAddMaster(false)}/>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 5. SHORT LINK ═════════════════════════════════ */}
      <Card>
        <SH step="5" title="Short Link" badge={`${shortLinks.length}`} keyName="short"/>
        {open.short && (
          <CardContent>
            <div className="mb-2 p-2 bg-sky-50 rounded border border-sky-200 text-xs text-sky-900">
              Short Link spans the shorter interior dimension. Enter actual link_width and link_depth, 
              or leave blank to derive from column dimensions and cover.
            </div>
            <ItemList items={shortLinks}
              labelFn={b=>`<strong>${b.link_mark}</strong> &nbsp; Ø${b.diameter}mm @ ${b.spacing}mm &nbsp; <span class='text-xs text-gray-500'>${b.zone_name||'full height'} / ${b.dimension_convention}</span>`}
              onRemove={i=>setShortLinks(shortLinks.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddShort(!showAddShort)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Short Link
            </Button>
            {showAddShort && (
              <LinkForm form={shortForm} setForm={setShortForm} label="Short Link"
                onAdd={()=>{
                  if(!shortForm.link_mark){toast.error('Link Mark required');return}
                  setShortLinks([...shortLinks,{...shortForm}])
                  setShortForm({...EMPTY_LINK,link_mark:'',number_of_legs:2}); setShowAddShort(false)
                  toast.success('Short link added')
                }}
                onCancel={()=>setShowAddShort(false)}/>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 6. LONG LINK ══════════════════════════════════ */}
      <Card>
        <SH step="6" title="Long Link" badge={`${longLinks.length}`} keyName="long"/>
        {open.long && (
          <CardContent>
            <div className="mb-2 p-2 bg-indigo-50 rounded border border-indigo-200 text-xs text-indigo-900">
              Long Link spans the longer interior dimension. It has a different cutting length from the Short Link.
            </div>
            <ItemList items={longLinks}
              labelFn={b=>`<strong>${b.link_mark}</strong> &nbsp; Ø${b.diameter}mm @ ${b.spacing}mm &nbsp; <span class='text-xs text-gray-500'>${b.zone_name||'full height'} / ${b.dimension_convention}</span>`}
              onRemove={i=>setLongLinks(longLinks.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddLong(!showAddLong)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Long Link
            </Button>
            {showAddLong && (
              <LinkForm form={longForm} setForm={setLongForm} label="Long Link"
                onAdd={()=>{
                  if(!longForm.link_mark){toast.error('Link Mark required');return}
                  setLongLinks([...longLinks,{...longForm}])
                  setLongForm({...EMPTY_LINK,link_mark:'',number_of_legs:2}); setShowAddLong(false)
                  toast.success('Long link added')
                }}
                onCancel={()=>setShowAddLong(false)}/>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 7. CROSS TIE ══════════════════════════════════ */}
      <Card>
        <SH step="7" title="Cross Tie" badge={`${crossTies.length}`} keyName="cross"/>
        {open.cross && (
          <CardContent>
            <ItemList items={crossTies}
              labelFn={b=>`<strong>${b.tie_mark}</strong> &nbsp; Ø${b.diameter}mm @ ${b.spacing}mm &nbsp; <span class='text-xs text-gray-500'>${b.zone_name||'full height'}</span>`}
              onRemove={i=>setCrossTies(crossTies.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddCrossTie(!showAddCrossTie)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Cross Tie
            </Button>
            {showAddCrossTie && (
              <CrossTieFormComp form={crossTieForm} setForm={setCrossTieForm}
                onAdd={()=>{
                  if(!crossTieForm.tie_mark){toast.error('Tie Mark required');return}
                  setCrossTies([...crossTies,{...crossTieForm}])
                  setCrossTieForm({...EMPTY_CROSS_TIE}); setShowAddCrossTie(false)
                  toast.success('Cross tie added')
                }}
                onCancel={()=>setShowAddCrossTie(false)}/>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 8. COLUMN ZONES ═══════════════════════════════ */}
      <Card>
        <SH step="8" title="Column Zones" badge={`${zones.length}`} keyName="zones"/>
        {open.zones && (
          <CardContent>
            <div className="mb-2 p-2 bg-gray-50 rounded border text-xs text-gray-700">
              Define zones (Confined, Regular, Lap Splice) with different link spacings. 
              Each zone can reference a specific link mark.
            </div>
            <ItemList items={zones}
              labelFn={b=>`<strong>${b.zone_name}</strong> &nbsp; <span class='text-xs text-gray-500'>${b.zone_type} · Link: ${b.link_mark||'—'} · @${b.spacing}mm</span>`}
              onRemove={i=>setZones(zones.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddZone(!showAddZone)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Zone
            </Button>
            {showAddZone && (
              <Card className="mt-3 border-gray-200">
                <CardContent className="p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inp('Zone Name *',    zoneForm.zone_name,    v=>setZoneForm({...zoneForm,zone_name:v}))}
                    {sel('Zone Type',      zoneForm.zone_type,    v=>setZoneForm({...zoneForm,zone_type:v}), ZONE_TYPES)}
                    {inp('Start Height (mm)', zoneForm.start_height, v=>setZoneForm({...zoneForm,start_height:v}), 'number','1')}
                    {inp('End Height (mm)',   zoneForm.end_height,   v=>setZoneForm({...zoneForm,end_height:v}), 'number','1')}
                    {inp('Link Mark',      zoneForm.link_mark,    v=>setZoneForm({...zoneForm,link_mark:v}))}
                    {inp('Spacing (mm)',   zoneForm.spacing,      v=>setZoneForm({...zoneForm,spacing:v}), 'number','1')}
                    {inp('Remarks',        zoneForm.remarks,      v=>setZoneForm({...zoneForm,remarks:v}))}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={()=>{
                      if(!zoneForm.zone_name){toast.error('Zone Name required');return}
                      setZones([...zones,{...zoneForm}])
                      setZoneForm({...EMPTY_ZONE}); setShowAddZone(false)
                      toast.success('Zone added')
                    }}>Add Zone</Button>
                    <Button size="sm" variant="ghost" onClick={()=>setShowAddZone(false)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ CALCULATE BUTTON ══════════════════════════════ */}
      <div className="flex gap-3 items-center">
        <Button size="lg" onClick={handleCalculate} disabled={calcMut.isPending}>
          <Calculator className="h-4 w-4 mr-2"/>
          {calcMut.isPending ? 'Calculating...' : 'Calculate Complete Column BBS'}
        </Button>
        {result && (
          <>
            <Button size="sm" variant="outline"
              onClick={()=>window.open(`http://localhost:8001/api/v1/bbs/${sheetId}/export/excel`)}>
              <Download className="h-3.5 w-3.5 mr-1"/> Excel
            </Button>
            <Button size="sm" variant="outline"
              onClick={()=>window.open(`http://localhost:8001/api/v1/bbs/${sheetId}/export/pdf`)}>
              <FileText className="h-3.5 w-3.5 mr-1"/> PDF
            </Button>
          </>
        )}
      </div>

      {/* ═══ UNIFIED COLUMN BBS RESULTS ════════════════════ */}
      {result && (
        <Card className="border-green-300">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600"/>
              Unified Column BBS — {result.member_info?.column_mark}
              <Badge className="bg-green-600 text-white ml-auto">IS 456 : 2000</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">

            {/* Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <SummaryCard label="Total Weight" value={`${(result.total_weight_kg??0).toFixed(2)} kg`} color="green"/>
              <SummaryCard label="Total Entries" value={String(result.unified_bbs_entries?.length??0)} color="blue"/>
              <SummaryCard label="Main Bar Wt"   value={`${(result.reinforcement_breakdown?.main_bar_weight_kg??0).toFixed(2)} kg`} color="purple"/>
              <SummaryCard label="Tie/Link Wt"   value={`${(result.reinforcement_breakdown?.tie_weight_kg??0).toFixed(2)} kg`} color="orange"/>
            </div>

            {/* Unified BBS table */}
            <div className="overflow-x-auto rounded border">
              <table className="w-full text-xs">
                <thead className="bg-primary text-white">
                  <tr>
                    {['Sr','Bar Mark','Type','Dia','No. Bars','Cut Length (mm)',
                      'Total Length (m)','Unit Wt (kg/m)','Total Wt (kg)','Trace'].map(h=>(
                      <th key={h} className="px-2 py-2 text-left whitespace-nowrap font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {(result.unified_bbs_entries??[]).map((e:any, i:number)=>{
                    const cl = e.length_of_each_bar ?? e.cutting_length_mm ?? 0
                    const tl = e.total_length ?? (cl * e.number_of_bars / 1000)
                    const uw = e.unit_weight  ?? (e.diameter**2/162)
                    const tw = e.total_weight ?? (tl * uw)
                    return (
                      <tr key={i} className="hover:bg-muted/30">
                        <td className="px-2 py-1.5">{i+1}</td>
                        <td className="px-2 py-1.5 font-semibold">{e.bar_mark}</td>
                        <td className="px-2 py-1.5 text-muted-foreground text-xs">{e.shape_code||e.bending_details||'—'}</td>
                        <td className="px-2 py-1.5 font-mono">{e.diameter}Ø</td>
                        <td className="px-2 py-1.5 text-right">{e.number_of_bars}</td>
                        <td className="px-2 py-1.5 text-right font-mono font-semibold">{Number(cl).toFixed(0)}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{Number(tl).toFixed(3)}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{Number(uw).toFixed(3)}</td>
                        <td className="px-2 py-1.5 text-right font-mono font-semibold">{Number(tw).toFixed(3)}</td>
                        <td className="px-2 py-1.5">
                          {e.calculation_trace && (
                            <Button size="icon" variant="ghost" className="h-6 w-6"
                              onClick={()=>setShowTrace(t=>({...t,[i]:!t[i]}))}>
                              <Info className="h-3 w-3"/>
                            </Button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                  <tr className="font-bold bg-muted/40">
                    <td colSpan={8} className="px-2 py-2 text-right">TOTAL COLUMN WEIGHT</td>
                    <td className="px-2 py-2 text-right text-primary font-bold">
                      {(result.total_weight_kg??0).toFixed(2)} kg
                    </td>
                    <td/>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Per-row calculation traces */}
            {(result.unified_bbs_entries??[]).map((e:any, i:number)=> showTrace[i] && e.calculation_trace && (
              <Card key={`trace-${i}`} className="border-purple-200 bg-purple-50/30">
                <CardContent className="p-3">
                  <p className="text-xs font-semibold text-purple-900 mb-2">Calculation Trace — {e.bar_mark}</p>
                  <CalcTrace trace={e.calculation_trace}/>
                </CardContent>
              </Card>
            ))}

            {/* Diameter summary */}
            {result.diameter_summary && Array.isArray(result.diameter_summary) && result.diameter_summary.length > 0 && (
              <div>
                <h4 className="font-semibold text-sm mb-2">Diameter-wise Summary</h4>
                <div className="overflow-x-auto rounded border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50">
                      <tr>
                        {['Dia (mm)','No. Bars','Total Length (m)','Unit Wt (kg/m)','Total Wt (kg)'].map(h=>(
                          <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {result.diameter_summary.map((d:any,idx:number)=>(
                        <tr key={d.dia_mm??d.diameter??idx} className="hover:bg-muted/30">
                          <td className="px-3 py-1.5 font-bold">{d.dia_mm??d.diameter}Ø</td>
                          <td className="px-3 py-1.5">{d.num_bars??d.number_of_bars}</td>
                          <td className="px-3 py-1.5 font-mono">{Number(d.total_length_m??d.total_length??0).toFixed(3)}</td>
                          <td className="px-3 py-1.5 font-mono">{((d.dia_mm??d.diameter)**2/162).toFixed(3)}</td>
                          <td className="px-3 py-1.5 font-mono font-semibold">{Number(d.total_weight_kg??d.total_weight??0).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function SummaryCard({ label, value, color }: { label:string, value:string, color:string }) {
  const bg = { green:'bg-green-50', blue:'bg-blue-50', purple:'bg-purple-50', orange:'bg-orange-50' }[color]
  const fc = { green:'text-green-700', blue:'text-blue-700', purple:'text-purple-700', orange:'text-orange-700' }[color]
  return (
    <div className={`p-3 rounded-lg ${bg}`}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-xl font-bold ${fc}`}>{value}</p>
    </div>
  )
}

function CalcTrace({ trace }: { trace: any }) {
  if (!trace) return null
  const rows: { label:string; value:string }[] = []
  if (trace.bar_mark)    rows.push({ label:'Bar Mark',    value:trace.bar_mark })
  if (trace.diameter_mm) rows.push({ label:'Diameter',    value:`${trace.diameter_mm} mm` })
  if (trace.formula)     rows.push({ label:'Formula',     value:trace.formula })
  if (trace.calculation) rows.push({ label:'Calculation', value:trace.calculation })
  const bd = trace.calculation_breakdown
  if (bd) Object.entries(bd).forEach(([k,v])=>rows.push({ label:k.replace(/_/g,' '), value:String(v) }))
  if (trace.lap_calculation) {
    const lc = trace.lap_calculation
    if (lc.formula)  rows.push({ label:'Lap Formula', value:lc.formula })
    if (lc.result||lc.lap_length_mm) rows.push({ label:'Lap Result', value:String(lc.result??lc.lap_length_mm) })
  }
  if (trace.development_calculation) {
    const dc = trace.development_calculation
    if (dc.formula) rows.push({ label:'Dev Length Formula', value:dc.formula })
    if (dc.result||dc.development_length_mm) rows.push({ label:'Dev Length Result', value:String(dc.result??dc.development_length_mm) })
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
      {rows.map((r,i)=>(
        <div key={i} className="flex gap-2">
          <dt className="text-muted-foreground shrink-0 capitalize">{r.label}:</dt>
          <dd className="font-mono text-primary break-all">{r.value}</dd>
        </div>
      ))}
    </dl>
  )
}
