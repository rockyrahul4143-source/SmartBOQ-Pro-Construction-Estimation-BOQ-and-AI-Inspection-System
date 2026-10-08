/**
 * ManualBeamBBS.tsx
 * Complete member-specific Manual Beam BBS UI.
 *
 * Sections:
 *  1. Beam Information
 *  2. Top Main / Continuous Bars
 *  3. Bottom Main / Continuous Bars
 *  4. Bottom Curtailed Bars
 *  5. Top Extra Left Bars
 *  6. Top Extra Right Bars
 *  7. Beam Stirrups (Left / Middle / Right zones)
 *  — Calculate Complete Beam BBS —
 *  8. Unified BBS Results table + Calculation Trace
 *  9. Export (Excel / PDF)
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Plus, Trash2, Calculator, Info, ChevronDown, ChevronUp,
  Download, FileText, AlertTriangle, CheckCircle2,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

/* ── static option lists ─────────────────────────────── */
const CONCRETE_GRADES = ['M15','M20','M25','M30','M35','M40','M45','M50']
const STEEL_GRADES    = ['FE415','FE500','FE550','FE600']
const BAR_DIAS        = [6,8,10,12,16,20,25,28,32,36,40]
const LAP_METHODS     = ['30D','40D','45D','50D','60D','DRAWING_SPECIFIED','CODE_BASED','CUSTOM']
const HOOK_TYPES      = ['90_DEGREE','135_DEGREE','180_DEGREE','45_DEGREE','STANDARD_HOOK','CUSTOM']
const CURTAIL_RULES   = ['L2','L3','L4','DRAWING_SPECIFIED','CUSTOM']
const EXTENSION_RULES = ['L4','L3','L2','DRAWING_SPECIFIED','CUSTOM']
const STIRRUP_SHAPES  = ['RECTANGULAR','SQUARE']
const ENDPOINT_CONVS  = ['BOTH_ENDS_INCLUDED','ONE_END','NO_ENDS','DRAWING_SPECIFIED']

/* ── helper: show lap length when multiplier is chosen ─ */
function lapPreview(method: string, dia: number) {
  const map: Record<string, number> = { '30D': 30,'40D': 40,'45D': 45,'50D': 50,'60D': 60 }
  if (map[method]) return `= ${map[method]} × ${dia} = ${map[method] * dia} mm`
  return null
}

/* ── unit weight formula helper ─────────────────────── */
const unitWt = (d: number) => (d * d / 162).toFixed(3)

interface Props { projectId: string; sheetId: string; sheet: any }

/* ── shared sub-forms ────────────────────────────────── */
const EMPTY_MAIN_BAR = {
  bar_mark:'', diameter:16, number_of_bars:2,
  left_anchorage_ld:'', right_anchorage_ld:'',
  lap_method:'CODE_BASED', lap_length:'',
  hook_near:null as string|null, hook_far:null as string|null, hook_extension:0,
  bend_shape:'straight', remarks:''
}
const EMPTY_CURTAILED = {
  bar_mark:'', diameter:16, number_of_bars:2,
  curtailment_rule:'L2', custom_length:'',
  anchorage_ld:'', lap_method:'CODE_BASED', lap_length:'',
  hook_type:null as string|null, hook_extension:0, remarks:''
}
const EMPTY_EXTRA = {
  bar_mark:'', diameter:16, number_of_bars:2,
  extension_rule:'L4', custom_extension:'',
  anchorage_ld:'', lap_method:'CODE_BASED', lap_length:'',
  hook_type:null as string|null, hook_extension:0, remarks:''
}
const EMPTY_STIRRUP_ZONE = {
  stirrup_mark:'', diameter:8, spacing:'', zone_length:'',
  number_of_legs:2, shape:'RECTANGULAR',
  hook_type:'135_DEGREE', hook_extension:75, bend_angle:135,
  endpoint_convention:'BOTH_ENDS_INCLUDED', remarks:''
}

export default function ManualBeamBBS({ projectId, sheetId, sheet }: Props) {

  /* ── beam info ────────────────────────────── */
  const [info, setInfo] = useState({
    building_tower:'', beam_mark:'',
    number_of_units:1, beam_width:'', beam_depth:'', clear_span:'',
    concrete_grade:'M25', steel_grade:'FE415', cover:25,
  })

  /* ── reinforcement lists ─────────────────── */
  const [topMainBars,       setTopMainBars]       = useState<any[]>([])
  const [bottomMainBars,    setBottomMainBars]     = useState<any[]>([])
  const [bottomCurtailed,   setBottomCurtailed]    = useState<any[]>([])
  const [topExtraLeft,      setTopExtraLeft]       = useState<any[]>([])
  const [topExtraRight,     setTopExtraRight]      = useState<any[]>([])

  /* ── add-form visibility ─────────────────── */
  const [showAddTopMain,    setShowAddTopMain]    = useState(false)
  const [showAddBotMain,    setShowAddBotMain]    = useState(false)
  const [showAddCurtailed,  setShowAddCurtailed]  = useState(false)
  const [showAddExtraLeft,  setShowAddExtraLeft]  = useState(false)
  const [showAddExtraRight, setShowAddExtraRight] = useState(false)

  /* ── add-form values ─────────────────────── */
  const [topMainForm,    setTopMainForm]    = useState<any>({...EMPTY_MAIN_BAR})
  const [botMainForm,    setBotMainForm]    = useState<any>({...EMPTY_MAIN_BAR})
  const [curtailedForm,  setCurtailedForm]  = useState<any>({...EMPTY_CURTAILED})
  const [extraLeftForm,  setExtraLeftForm]  = useState<any>({...EMPTY_EXTRA})
  const [extraRightForm, setExtraRightForm] = useState<any>({...EMPTY_EXTRA})

  /* ── stirrup zones ───────────────────────── */
  const [leftZone,   setLeftZone]   = useState<any>({...EMPTY_STIRRUP_ZONE, stirrup_mark:'', spacing:100})
  const [midZone,    setMidZone]    = useState<any>({...EMPTY_STIRRUP_ZONE, stirrup_mark:'', spacing:150})
  const [rightZone,  setRightZone]  = useState<any>({...EMPTY_STIRRUP_ZONE, stirrup_mark:'', spacing:100})

  /* ── section collapse ────────────────────── */
  const [open, setOpen] = useState<Record<string,boolean>>({
    info:true, topMain:false, botMain:false, curtailed:false,
    extraLeft:false, extraRight:false, stirrups:false
  })
  const toggle = (k: string) => setOpen(o => ({...o, [k]:!o[k]}))

  /* ── result ──────────────────────────────── */
  const [result, setResult] = useState<any>(null)
  const [showTrace, setShowTrace] = useState<Record<number,boolean>>({})

  /* ── calc mutation ───────────────────────── */
  const calcMut = useMutation({
    mutationFn: (d: any) => api.post('/bbs/complete/beam', d),
    onSuccess: ({ data }) => { 
      // Validate response structure before setting
      if (!data) {
        toast.error('Invalid response: no data returned');
        return;
      }
      
      // Ensure arrays exist
      if (data.bbs_entries && !Array.isArray(data.bbs_entries)) {
        console.error('bbs_entries is not an array:', data.bbs_entries);
        toast.error('Invalid response structure: bbs_entries must be an array');
        return;
      }
      
      if (data.diameter_summary && !Array.isArray(data.diameter_summary)) {
        console.error('diameter_summary is not an array:', data.diameter_summary);
        toast.error('Invalid response structure: diameter_summary must be an array');
        return;
      }
      
      setResult(data); 
      toast.success('Beam BBS calculated!');
    },
    onError: (e: any) => {
      console.error('Beam BBS calculation error:', e);
      const errorMsg = e.response?.data?.detail ?? e.message ?? 'Calculation failed';
      toast.error(errorMsg);
    },
  })

  const handleCalculate = () => {
    if (!info.beam_mark)   { toast.error('Beam Mark is required');   return }
    if (!info.beam_width)  { toast.error('Beam Width is required');  return }
    if (!info.beam_depth)  { toast.error('Beam Depth is required');  return }
    if (!info.clear_span)  { toast.error('Clear Span is required');  return }
    calcMut.mutate({
      ...info,
      project: projectId,
      beam_width: Number(info.beam_width),
      beam_depth: Number(info.beam_depth),
      clear_span: Number(info.clear_span),
      cover: Number(info.cover),
      number_of_units: Number(info.number_of_units),
      top_main_bars:         topMainBars,
      bottom_main_bars:      bottomMainBars,
      bottom_curtailed_bars: bottomCurtailed,
      top_extra_left_bars:   topExtraLeft,
      top_extra_right_bars:  topExtraRight,
      left_stirrup_zone:     leftZone.stirrup_mark  ? cleanZone(leftZone)  : null,
      middle_stirrup_zone:   midZone.stirrup_mark   ? cleanZone(midZone)   : null,
      right_stirrup_zone:    rightZone.stirrup_mark ? cleanZone(rightZone) : null,
    })
  }

  function cleanZone(z: any) {
    return { ...z, spacing: Number(z.spacing), zone_length: Number(z.zone_length) || undefined }
  }

  /* ── render helpers ──────────────────────── */
  const inp = (label: string, val: any, set: (v:any)=>void, type='text', step='1') => (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input type={type} step={step} value={val??''} className="h-8 text-sm"
        onChange={e => set(type==='number'
          ? (e.target.value==='' ? '' : Number(e.target.value))
          : e.target.value)} />
    </div>
  )
  const sel = (label: string, val: any, set: (v:any)=>void, opts: string[]) => (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Select value={String(val)} onValueChange={set}>
        <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
        <SelectContent>{opts.map(o=><SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  )

  /* ── generic main bar add form ───────────── */
  function MainBarForm({ form, setForm, onAdd, onCancel }: any) {
    const hookOpts = ['— No Hook —', ...HOOK_TYPES]
    return (
      <Card className="mb-3 border-blue-200">
        <CardContent className="p-3 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {inp('Bar Mark *',         form.bar_mark,          v=>setForm({...form,bar_mark:v}))}
            {sel('Diameter (mm) *',    String(form.diameter),  v=>setForm({...form,diameter:Number(v)}), BAR_DIAS.map(String))}
            {inp('No. of Bars *',      form.number_of_bars,    v=>setForm({...form,number_of_bars:v}), 'number','1')}
            {inp('Left Anchorage/Ld (mm)', form.left_anchorage_ld, v=>setForm({...form,left_anchorage_ld:v}), 'number','1')}
            {inp('Right Anchorage/Ld (mm)',form.right_anchorage_ld,v=>setForm({...form,right_anchorage_ld:v}),'number','1')}
            {sel('Lap Method',         form.lap_method,        v=>setForm({...form,lap_method:v}), LAP_METHODS)}
            {['DRAWING_SPECIFIED','CUSTOM'].includes(form.lap_method) &&
              inp('Lap Length (mm)', form.lap_length, v=>setForm({...form,lap_length:v}), 'number','1')}
            {sel('Hook Near',  form.hook_near||'— No Hook —',  v=>setForm({...form,hook_near:v==='— No Hook —'?null:v}),  hookOpts)}
            {sel('Hook Far',   form.hook_far||'— No Hook —',   v=>setForm({...form,hook_far:v==='— No Hook —'?null:v}),   hookOpts)}
            {(form.hook_near||form.hook_far) &&
              inp('Hook Extension (mm)', form.hook_extension, v=>setForm({...form,hook_extension:v}), 'number','1')}
            {inp('Remarks', form.remarks, v=>setForm({...form,remarks:v}))}
          </div>
          {/* Live lap preview */}
          {lapPreview(form.lap_method, form.diameter) && (
            <p className="text-xs text-blue-700 bg-blue-50 px-2 py-1 rounded">
              Lap: {lapPreview(form.lap_method, form.diameter)}
            </p>
          )}
          {/* Unit weight preview */}
          <p className="text-xs text-muted-foreground">
            Unit Weight: {form.diameter}² / 162 = <strong>{unitWt(form.diameter)} kg/m</strong>
          </p>
          <div className="flex gap-2">
            <Button size="sm" onClick={onAdd}>Add Bar</Button>
            <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  function BarList({ bars, onRemove }: { bars: any[], onRemove: (i:number)=>void }) {
    if (!bars.length) return null
    return (
      <div className="space-y-1.5 mb-2">
        {bars.map((b,i)=>(
          <div key={i} className="flex items-center justify-between px-3 py-2 bg-muted/30 rounded border text-sm">
            <span>
              <span className="font-semibold">{b.bar_mark}</span>
              <span className="ml-2 text-muted-foreground">{b.number_of_bars} × Ø{b.diameter}mm</span>
              <span className="ml-2 text-xs text-blue-700">{b.lap_method}</span>
              {lapPreview(b.lap_method, b.diameter) &&
                <span className="ml-2 text-xs text-green-700">{lapPreview(b.lap_method, b.diameter)}</span>}
            </span>
            <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive" onClick={()=>onRemove(i)}>
              <Trash2 className="h-3 w-3"/>
            </Button>
          </div>
        ))}
      </div>
    )
  }

  /* ── stirrup zone form ───────────────────── */
  function StirrupZoneForm({ label, zone, setZone, beamWidth, beamDepth, cover }: any) {
    const d = Number(zone.diameter)
    const w = Number(beamWidth)  || 0
    const h = Number(beamDepth)  || 0
    const c = Number(cover)      || 25
    // inside dimension cutting length preview
    const inner_w = w - 2*c - d
    const inner_h = h - 2*c - d
    const hook_ext = Number(zone.hook_extension) || 0
    // standard IS 456 hook allowance for 135° = 2 × hook_extension
    const hook_allow = zone.hook_type === 'NONE' ? 0 : (hook_ext * 2)
    // standard bend deduction for 135° = 3d
    const bend_ded = zone.hook_type === 'STANDARD_135' ? 3*d : (zone.hook_type === 'STANDARD_90' ? 2*d : 0)
    const cl_preview = inner_w > 0 && inner_h > 0
      ? (2*inner_w + 2*inner_h + hook_allow - bend_ded)
      : null

    const sp = Number(zone.spacing) || 0
    const zl = Number(zone.zone_length) || 0
    const n_preview = sp > 0 && zl > 0 ? Math.floor(zl / sp) + 1 : null

    return (
      <div className="border rounded-lg p-3 bg-muted/20">
        <h4 className="font-semibold text-sm mb-3">{label}</h4>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {inp('Stirrup Mark',   zone.stirrup_mark,   v=>setZone({...zone,stirrup_mark:v}))}
          {sel('Diameter (mm)', String(zone.diameter), v=>setZone({...zone,diameter:Number(v)}), BAR_DIAS.map(String))}
          {inp('Spacing (mm) *', zone.spacing,        v=>setZone({...zone,spacing:v}), 'number','1')}
          {inp('Zone Length (mm)', zone.zone_length,  v=>setZone({...zone,zone_length:v}), 'number','1')}
          {inp('No. of Legs',    zone.number_of_legs, v=>setZone({...zone,number_of_legs:v}), 'number','1')}
          {sel('Shape',          zone.shape,          v=>setZone({...zone,shape:v}), STIRRUP_SHAPES)}
          {sel('Hook Type',      zone.hook_type,      v=>setZone({...zone,hook_type:v}), HOOK_TYPES)}
          {inp('Hook Extension (mm)', zone.hook_extension, v=>setZone({...zone,hook_extension:v}), 'number','1')}
          {sel('Endpoint Convention', zone.endpoint_convention, v=>setZone({...zone,endpoint_convention:v}), ENDPOINT_CONVS)}
          {inp('Remarks',        zone.remarks,         v=>setZone({...zone,remarks:v}))}
        </div>
        {/* Live calculation preview */}
        {cl_preview !== null && (
          <div className="mt-2 p-2 bg-green-50 rounded text-xs space-y-0.5">
            <p className="font-semibold text-green-800">Live Cutting Length Preview (Inside Dimension):</p>
            <p>Inner Width = {w} − 2×{c} − {d} = <strong>{inner_w} mm</strong></p>
            <p>Inner Depth = {h} − 2×{c} − {d} = <strong>{inner_h} mm</strong></p>
            <p>CL = 2×{inner_w} + 2×{inner_h} + {hook_allow} (hooks) − {bend_ded} (bends) = <strong>{cl_preview.toFixed(0)} mm</strong></p>
            {n_preview !== null && (
              <p>No. of Stirrups (L/s+1) = {zl}/{sp}+1 = <strong>{n_preview}</strong></p>
            )}
            <p>Unit Wt = {d}²/162 = <strong>{unitWt(d)} kg/m</strong></p>
          </div>
        )}
      </div>
    )
  }

  /* ── section header ──────────────────────── */
  const SectionHeader = ({ step, title, badge, keyName }: any) => (
    <CardHeader className="pb-2 cursor-pointer select-none" onClick={()=>toggle(keyName)}>
      <div className="flex items-center justify-between">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="bg-primary text-white rounded-full w-6 h-6 flex items-center justify-center text-xs shrink-0">{step}</span>
          {title}
          {badge !== undefined && <Badge variant="outline">{badge}</Badge>}
        </CardTitle>
        {open[keyName] ? <ChevronUp className="h-4 w-4 shrink-0"/> : <ChevronDown className="h-4 w-4 shrink-0"/>}
      </div>
    </CardHeader>
  )

  return (
    <div className="space-y-4">

      {/* workflow guide */}
      <Card className="border-blue-200 bg-blue-50/40">
        <CardContent className="p-3 flex gap-2">
          <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0"/>
          <p className="text-xs text-blue-900">
            <strong>Beam BBS Workflow:</strong> Fill Beam Info → Add each reinforcement section → 
            Configure Stirrup Zones → Calculate → Review BBS table → Export Excel/PDF.
            Cutting lengths are derived from your actual inputs. No hardcoded values.
          </p>
        </CardContent>
      </Card>

      {/* ═══ 1. BEAM INFORMATION ═══════════════════════════ */}
      <Card>
        <SectionHeader step="1" title="Beam Information" keyName="info"/>
        {open.info && (
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {inp('Building / Tower',   info.building_tower,    v=>setInfo({...info,building_tower:v}))}
              {inp('Beam Mark *',        info.beam_mark,         v=>setInfo({...info,beam_mark:v}))}
              {inp('No. of Units',       info.number_of_units,   v=>setInfo({...info,number_of_units:v}), 'number','1')}
              {inp('Beam Width (mm) *',  info.beam_width,        v=>setInfo({...info,beam_width:v}), 'number','1')}
              {inp('Beam Depth (mm) *',  info.beam_depth,        v=>setInfo({...info,beam_depth:v}), 'number','1')}
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Beam Size</Label>
                <div className="h-8 flex items-center px-3 rounded border bg-muted/40 text-sm font-mono text-muted-foreground">
                  {info.beam_width && info.beam_depth ? `${info.beam_width} × ${info.beam_depth} mm` : '— × — mm'}
                </div>
              </div>
              {inp('Clear Span (mm) *',  info.clear_span,        v=>setInfo({...info,clear_span:v}), 'number','1')}
              {sel('Concrete Grade',     info.concrete_grade,    v=>setInfo({...info,concrete_grade:v}), CONCRETE_GRADES)}
              {sel('Steel Grade',        info.steel_grade,       v=>setInfo({...info,steel_grade:v}), STEEL_GRADES)}
              {inp('Clear Cover (mm)',   info.cover,             v=>setInfo({...info,cover:v}), 'number','1')}
            </div>
          </CardContent>
        )}
      </Card>

      {/* ═══ 2. TOP MAIN BARS ══════════════════════════════ */}
      <Card>
        <SectionHeader step="2" title="Top Main / Continuous Bars" badge={`${topMainBars.length} bars`} keyName="topMain"/>
        {open.topMain && (
          <CardContent>
            <BarList bars={topMainBars} onRemove={i=>setTopMainBars(topMainBars.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddTopMain(!showAddTopMain)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Top Main Bar
            </Button>
            {showAddTopMain && (
              <div className="mt-3">
                <MainBarForm form={topMainForm} setForm={setTopMainForm}
                  onAdd={()=>{
                    if(!topMainForm.bar_mark){toast.error('Bar Mark required');return}
                    setTopMainBars([...topMainBars,{...topMainForm}])
                    setTopMainForm({...EMPTY_MAIN_BAR})
                    setShowAddTopMain(false)
                    toast.success('Top main bar added')
                  }}
                  onCancel={()=>setShowAddTopMain(false)}/>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 3. BOTTOM MAIN BARS ═══════════════════════════ */}
      <Card>
        <SectionHeader step="3" title="Bottom Main / Continuous Bars" badge={`${bottomMainBars.length} bars`} keyName="botMain"/>
        {open.botMain && (
          <CardContent>
            <BarList bars={bottomMainBars} onRemove={i=>setBottomMainBars(bottomMainBars.filter((_,x)=>x!==i))}/>
            <Button size="sm" variant="outline" onClick={()=>setShowAddBotMain(!showAddBotMain)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Bottom Main Bar
            </Button>
            {showAddBotMain && (
              <div className="mt-3">
                <MainBarForm form={botMainForm} setForm={setBotMainForm}
                  onAdd={()=>{
                    if(!botMainForm.bar_mark){toast.error('Bar Mark required');return}
                    setBottomMainBars([...bottomMainBars,{...botMainForm}])
                    setBotMainForm({...EMPTY_MAIN_BAR})
                    setShowAddBotMain(false)
                    toast.success('Bottom main bar added')
                  }}
                  onCancel={()=>setShowAddBotMain(false)}/>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 4. BOTTOM CURTAILED ═══════════════════════════ */}
      <Card>
        <SectionHeader step="4" title="Bottom Curtailed / Mid-Span Bars" badge={`${bottomCurtailed.length} bars`} keyName="curtailed"/>
        {open.curtailed && (
          <CardContent>
            {bottomCurtailed.length > 0 && (
              <div className="space-y-1.5 mb-2">
                {bottomCurtailed.map((b,i)=>(
                  <div key={i} className="flex items-center justify-between px-3 py-2 bg-muted/30 rounded border text-sm">
                    <span>
                      <span className="font-semibold">{b.bar_mark}</span>
                      <span className="ml-2 text-muted-foreground">{b.number_of_bars}×Ø{b.diameter}mm</span>
                      <Badge variant="outline" className="ml-2 text-xs">{b.curtailment_rule}</Badge>
                    </span>
                    <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive"
                      onClick={()=>setBottomCurtailed(bottomCurtailed.filter((_,x)=>x!==i))}>
                      <Trash2 className="h-3 w-3"/>
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <Button size="sm" variant="outline" onClick={()=>setShowAddCurtailed(!showAddCurtailed)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Curtailed Bar
            </Button>
            {showAddCurtailed && (
              <Card className="mt-3 border-amber-200">
                <CardContent className="p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inp('Bar Mark *',         curtailedForm.bar_mark,       v=>setCurtailedForm({...curtailedForm,bar_mark:v}))}
                    {sel('Diameter (mm)',       String(curtailedForm.diameter),v=>setCurtailedForm({...curtailedForm,diameter:Number(v)}), BAR_DIAS.map(String))}
                    {inp('No. of Bars',        curtailedForm.number_of_bars, v=>setCurtailedForm({...curtailedForm,number_of_bars:v}), 'number','1')}
                    {sel('Curtailment Rule',   curtailedForm.curtailment_rule,v=>setCurtailedForm({...curtailedForm,curtailment_rule:v}), CURTAIL_RULES)}
                    {curtailedForm.curtailment_rule==='CUSTOM' &&
                      inp('Custom Length (mm)', curtailedForm.custom_length, v=>setCurtailedForm({...curtailedForm,custom_length:v}), 'number','1')}
                    {inp('Anchorage/Ld (mm)',  curtailedForm.anchorage_ld,   v=>setCurtailedForm({...curtailedForm,anchorage_ld:v}), 'number','1')}
                    {sel('Lap Method',         curtailedForm.lap_method,     v=>setCurtailedForm({...curtailedForm,lap_method:v}), LAP_METHODS)}
                    {['DRAWING_SPECIFIED','CUSTOM'].includes(curtailedForm.lap_method) &&
                      inp('Lap Length (mm)',   curtailedForm.lap_length,     v=>setCurtailedForm({...curtailedForm,lap_length:v}), 'number','1')}
                    {sel('Hook Type',          curtailedForm.hook_type,      v=>setCurtailedForm({...curtailedForm,hook_type:v}), HOOK_TYPES)}
                    {curtailedForm.hook_type!=='NONE' &&
                      inp('Hook Extension (mm)',curtailedForm.hook_extension,v=>setCurtailedForm({...curtailedForm,hook_extension:v}), 'number','1')}
                    {inp('Remarks',            curtailedForm.remarks,        v=>setCurtailedForm({...curtailedForm,remarks:v}))}
                  </div>
                  {/* curtailment length preview */}
                  {info.clear_span && (
                    <div className="text-xs text-muted-foreground bg-muted/40 px-2 py-1 rounded">
                      {curtailedForm.curtailment_rule==='L2' && `Curtail = ${info.clear_span}/2 = ${Number(info.clear_span)/2} mm`}
                      {curtailedForm.curtailment_rule==='L3' && `Curtail = ${info.clear_span}/3 = ${(Number(info.clear_span)/3).toFixed(0)} mm`}
                      {curtailedForm.curtailment_rule==='L4' && `Curtail = ${info.clear_span}/4 = ${Number(info.clear_span)/4} mm`}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button size="sm" onClick={()=>{
                      if(!curtailedForm.bar_mark){toast.error('Bar Mark required');return}
                      setBottomCurtailed([...bottomCurtailed,{...curtailedForm}])
                      setCurtailedForm({...EMPTY_CURTAILED}); setShowAddCurtailed(false)
                      toast.success('Curtailed bar added')
                    }}>Add Bar</Button>
                    <Button size="sm" variant="ghost" onClick={()=>setShowAddCurtailed(false)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 5. TOP EXTRA LEFT ═════════════════════════════ */}
      <Card>
        <SectionHeader step="5" title="Top Extra Left Bars" badge={`${topExtraLeft.length} bars`} keyName="extraLeft"/>
        {open.extraLeft && (
          <CardContent>
            {topExtraLeft.length > 0 && (
              <div className="space-y-1.5 mb-2">
                {topExtraLeft.map((b,i)=>(
                  <div key={i} className="flex items-center justify-between px-3 py-2 bg-muted/30 rounded border text-sm">
                    <span>
                      <span className="font-semibold">{b.bar_mark}</span>
                      <span className="ml-2 text-muted-foreground">{b.number_of_bars}×Ø{b.diameter}mm</span>
                      <Badge variant="outline" className="ml-2 text-xs">{b.extension_rule}</Badge>
                    </span>
                    <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive"
                      onClick={()=>setTopExtraLeft(topExtraLeft.filter((_,x)=>x!==i))}>
                      <Trash2 className="h-3 w-3"/>
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <Button size="sm" variant="outline" onClick={()=>setShowAddExtraLeft(!showAddExtraLeft)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Top Extra Left Bar
            </Button>
            {showAddExtraLeft && (
              <Card className="mt-3 border-purple-200">
                <CardContent className="p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inp('Bar Mark *',         extraLeftForm.bar_mark,       v=>setExtraLeftForm({...extraLeftForm,bar_mark:v}))}
                    {sel('Diameter (mm)',       String(extraLeftForm.diameter),v=>setExtraLeftForm({...extraLeftForm,diameter:Number(v)}), BAR_DIAS.map(String))}
                    {inp('No. of Bars',        extraLeftForm.number_of_bars, v=>setExtraLeftForm({...extraLeftForm,number_of_bars:v}), 'number','1')}
                    {sel('Extension Rule',     extraLeftForm.extension_rule, v=>setExtraLeftForm({...extraLeftForm,extension_rule:v}), EXTENSION_RULES)}
                    {extraLeftForm.extension_rule==='CUSTOM' &&
                      inp('Custom Extension (mm)', extraLeftForm.custom_extension, v=>setExtraLeftForm({...extraLeftForm,custom_extension:v}), 'number','1')}
                    {inp('Anchorage/Ld (mm)',  extraLeftForm.anchorage_ld,   v=>setExtraLeftForm({...extraLeftForm,anchorage_ld:v}), 'number','1')}
                    {sel('Hook Type',          extraLeftForm.hook_type,      v=>setExtraLeftForm({...extraLeftForm,hook_type:v}), HOOK_TYPES)}
                    {extraLeftForm.hook_type!=='NONE' &&
                      inp('Hook Extension (mm)',extraLeftForm.hook_extension,v=>setExtraLeftForm({...extraLeftForm,hook_extension:v}), 'number','1')}
                    {inp('Remarks',            extraLeftForm.remarks,        v=>setExtraLeftForm({...extraLeftForm,remarks:v}))}
                  </div>
                  {info.clear_span && (
                    <p className="text-xs text-muted-foreground">
                      {extraLeftForm.extension_rule==='L4' && `Extension = ${info.clear_span}/4 = ${Number(info.clear_span)/4} mm`}
                      {extraLeftForm.extension_rule==='L3' && `Extension = ${info.clear_span}/3 = ${(Number(info.clear_span)/3).toFixed(0)} mm`}
                      {extraLeftForm.extension_rule==='L2' && `Extension = ${info.clear_span}/2 = ${Number(info.clear_span)/2} mm`}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button size="sm" onClick={()=>{
                      if(!extraLeftForm.bar_mark){toast.error('Bar Mark required');return}
                      setTopExtraLeft([...topExtraLeft,{...extraLeftForm}])
                      setExtraLeftForm({...EMPTY_EXTRA}); setShowAddExtraLeft(false)
                      toast.success('Top extra left bar added')
                    }}>Add Bar</Button>
                    <Button size="sm" variant="ghost" onClick={()=>setShowAddExtraLeft(false)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 6. TOP EXTRA RIGHT ════════════════════════════ */}
      <Card>
        <SectionHeader step="6" title="Top Extra Right Bars" badge={`${topExtraRight.length} bars`} keyName="extraRight"/>
        {open.extraRight && (
          <CardContent>
            {topExtraRight.length > 0 && (
              <div className="space-y-1.5 mb-2">
                {topExtraRight.map((b,i)=>(
                  <div key={i} className="flex items-center justify-between px-3 py-2 bg-muted/30 rounded border text-sm">
                    <span>
                      <span className="font-semibold">{b.bar_mark}</span>
                      <span className="ml-2 text-muted-foreground">{b.number_of_bars}×Ø{b.diameter}mm</span>
                      <Badge variant="outline" className="ml-2 text-xs">{b.extension_rule}</Badge>
                    </span>
                    <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive"
                      onClick={()=>setTopExtraRight(topExtraRight.filter((_,x)=>x!==i))}>
                      <Trash2 className="h-3 w-3"/>
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <Button size="sm" variant="outline" onClick={()=>setShowAddExtraRight(!showAddExtraRight)}>
              <Plus className="h-3.5 w-3.5 mr-1"/> Add Top Extra Right Bar
            </Button>
            {showAddExtraRight && (
              <Card className="mt-3 border-purple-200">
                <CardContent className="p-3 space-y-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {inp('Bar Mark *',         extraRightForm.bar_mark,        v=>setExtraRightForm({...extraRightForm,bar_mark:v}))}
                    {sel('Diameter (mm)',       String(extraRightForm.diameter), v=>setExtraRightForm({...extraRightForm,diameter:Number(v)}), BAR_DIAS.map(String))}
                    {inp('No. of Bars',        extraRightForm.number_of_bars,  v=>setExtraRightForm({...extraRightForm,number_of_bars:v}), 'number','1')}
                    {sel('Extension Rule',     extraRightForm.extension_rule,  v=>setExtraRightForm({...extraRightForm,extension_rule:v}), EXTENSION_RULES)}
                    {extraRightForm.extension_rule==='CUSTOM' &&
                      inp('Custom Extension (mm)', extraRightForm.custom_extension, v=>setExtraRightForm({...extraRightForm,custom_extension:v}), 'number','1')}
                    {inp('Anchorage/Ld (mm)',  extraRightForm.anchorage_ld,    v=>setExtraRightForm({...extraRightForm,anchorage_ld:v}), 'number','1')}
                    {sel('Hook Type',          extraRightForm.hook_type,       v=>setExtraRightForm({...extraRightForm,hook_type:v}), HOOK_TYPES)}
                    {extraRightForm.hook_type!=='NONE' &&
                      inp('Hook Extension (mm)',extraRightForm.hook_extension, v=>setExtraRightForm({...extraRightForm,hook_extension:v}), 'number','1')}
                    {inp('Remarks',            extraRightForm.remarks,         v=>setExtraRightForm({...extraRightForm,remarks:v}))}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={()=>{
                      if(!extraRightForm.bar_mark){toast.error('Bar Mark required');return}
                      setTopExtraRight([...topExtraRight,{...extraRightForm}])
                      setExtraRightForm({...EMPTY_EXTRA}); setShowAddExtraRight(false)
                      toast.success('Top extra right bar added')
                    }}>Add Bar</Button>
                    <Button size="sm" variant="ghost" onClick={()=>setShowAddExtraRight(false)}>Cancel</Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </CardContent>
        )}
      </Card>

      {/* ═══ 7. STIRRUP ZONES ══════════════════════════════ */}
      <Card>
        <SectionHeader step="7" title="Beam Stirrups — Left / Middle / Right Zones" keyName="stirrups"/>
        {open.stirrups && (
          <CardContent className="space-y-4">
            <div className="p-3 bg-amber-50 rounded border border-amber-200">
              <p className="text-xs text-amber-900">
                <strong>Each zone is independent.</strong> Cutting length is calculated from beam dimensions + cover + 
                stirrup diameter + hooks. Quantity = zone_length / spacing + 1 (both-ends convention).
                If Drawing Specified, enter quantity directly in Remarks.
              </p>
            </div>
            <StirrupZoneForm label="Left / Support Zone" zone={leftZone} setZone={setLeftZone}
              beamWidth={info.beam_width} beamDepth={info.beam_depth} cover={info.cover}/>
            <StirrupZoneForm label="Middle Zone" zone={midZone} setZone={setMidZone}
              beamWidth={info.beam_width} beamDepth={info.beam_depth} cover={info.cover}/>
            <StirrupZoneForm label="Right / Support Zone" zone={rightZone} setZone={setRightZone}
              beamWidth={info.beam_width} beamDepth={info.beam_depth} cover={info.cover}/>
          </CardContent>
        )}
      </Card>

      {/* ═══ CALCULATE BUTTON ══════════════════════════════ */}
      <div className="flex gap-3 items-center">
        <Button size="lg" onClick={handleCalculate} disabled={calcMut.isPending}>
          <Calculator className="h-4 w-4 mr-2"/>
          {calcMut.isPending ? 'Calculating...' : 'Calculate Complete Beam BBS'}
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

      {/* ═══ BBS RESULTS ═══════════════════════════════════ */}
      {result && (
        <Card className="border-green-300">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600"/>
              Beam BBS — {result.member_info?.beam_mark}
              <Badge className="bg-green-600 text-white ml-auto">IS 456 : 2000</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">

            {/* Summary cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <SummaryCard label="Total Weight" value={`${(result.total_weight_kg??0).toFixed(2)} kg`} color="green"/>
              <SummaryCard label="Total Entries" value={String(result.bbs_entries?.length??0)} color="blue"/>
              <SummaryCard label="Main Bar Wt" value={`${(result.member_summaries?.main_bars_weight_kg??0).toFixed(2)} kg`} color="purple"/>
              <SummaryCard label="Stirrup Wt"  value={`${(result.member_summaries?.stirrups_weight_kg??0).toFixed(2)} kg`} color="orange"/>
            </div>

            {/* BBS Table */}
            <div className="overflow-x-auto rounded border">
              <table className="w-full text-xs">
                <thead className="bg-primary text-white">
                  <tr>
                    {['Sr','Bar Mark','Type','Dia (mm)','No. Bars','Cut Length (mm)',
                      'Total Length (m)','Unit Wt (kg/m)','Total Wt (kg)','Trace'].map(h=>(
                      <th key={h} className="px-2 py-2 text-left whitespace-nowrap font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {(result.bbs_entries??[]).map((e:any, i:number)=>{
                    const cl   = e.length_of_each_bar ?? e.cutting_length_mm ?? 0
                    const tl   = e.total_length ?? (cl * e.number_of_bars / 1000)
                    const uw   = e.unit_weight  ?? (e.diameter**2/162)
                    const tw   = e.total_weight ?? (tl * uw)
                    return (
                      <tr key={i} className="hover:bg-muted/30">
                        <td className="px-2 py-1.5">{i+1}</td>
                        <td className="px-2 py-1.5 font-semibold">{e.bar_mark}</td>
                        <td className="px-2 py-1.5 text-muted-foreground">{e.shape_code||e.bending_details||'—'}</td>
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
                  {/* Totals row */}
                  <tr className="font-bold bg-muted/40">
                    <td colSpan={8} className="px-2 py-2 text-right">TOTAL BEAM WEIGHT</td>
                    <td className="px-2 py-2 text-right text-primary font-bold">
                      {(result.total_weight_kg??0).toFixed(2)} kg
                    </td>
                    <td/>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Per-row calculation trace */}
            {(result.bbs_entries??[]).map((e:any, i:number)=> showTrace[i] && e.calculation_trace && (
              <Card key={`trace-${i}`} className="border-blue-200 bg-blue-50/30">
                <CardContent className="p-3">
                  <p className="text-xs font-semibold text-blue-900 mb-2">
                    Calculation Trace — {e.bar_mark}
                  </p>
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

/* ── shared summary card ─────────────────────────────── */
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

/* ── calculation trace renderer ──────────────────────── */
function CalcTrace({ trace }: { trace: any }) {
  if (!trace) return null
  const rows: { label: string; value: string }[] = []

  // standard fields
  if (trace.bar_mark)      rows.push({ label: 'Bar Mark',       value: trace.bar_mark })
  if (trace.diameter_mm)   rows.push({ label: 'Diameter',       value: `${trace.diameter_mm} mm` })
  if (trace.formula)       rows.push({ label: 'Formula',        value: trace.formula })
  if (trace.calculation)   rows.push({ label: 'Calculation',    value: trace.calculation })

  // breakdown
  const bd = trace.calculation_breakdown
  if (bd) {
    Object.entries(bd).forEach(([k,v])=> rows.push({ label: k.replace(/_/g,' '), value: String(v) }))
  }
  // lap
  if (trace.lap_calculation) {
    const lc = trace.lap_calculation
    rows.push({ label: 'Lap Formula',  value: lc.formula  ?? '' })
    rows.push({ label: 'Lap Result',   value: lc.result   ?? lc.lap_length_mm ?? '' })
  }
  // dev length
  if (trace.development_calculation) {
    const dc = trace.development_calculation
    rows.push({ label: 'Dev Length Formula', value: dc.formula ?? '' })
    rows.push({ label: 'Dev Length Result',  value: dc.result  ?? dc.development_length_mm ?? '' })
  }

  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
      {rows.map((r,i)=>(
        <div key={i} className="flex gap-2">
          <dt className="text-muted-foreground shrink-0 capitalize">{r.label}:</dt>
          <dd className="font-mono text-primary break-all">{String(r.value)}</dd>
        </div>
      ))}
    </dl>
  )
}
