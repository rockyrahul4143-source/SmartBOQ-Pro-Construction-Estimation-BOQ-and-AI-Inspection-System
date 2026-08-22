import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Eye, Upload, AlertTriangle, CheckCircle2, Loader2, History, Shield, Zap, Clock } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { severityColor, capitalize, formatDate } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

const INSPECTION_TYPES = [
  {
    value: 'concrete_crack',
    label: 'Concrete Crack Detection',
    icon: Zap,
    endpoint: '/inspection/concrete-crack',
    desc: 'CNN binary classifier — Crack / No Crack (99.9% accuracy)',
    color: 'bg-blue-50 border-blue-200 text-blue-800',
  },
  {
    value: 'surface_crack',
    label: 'Surface Crack Ensemble',
    icon: Zap,
    endpoint: '/inspection/surface-crack',
    desc: 'ResNet50 + InceptionV3 + VGG16 soft-voting ensemble',
    color: 'bg-purple-50 border-purple-200 text-purple-800',
  },
  {
    value: 'road_damage',
    label: 'Road Damage & Potholes',
    icon: AlertTriangle,
    endpoint: '/inspection/road-damage',
    desc: 'Faster R-CNN object detection — crack, damage, pothole',
    color: 'bg-orange-50 border-orange-200 text-orange-800',
  },
  {
    value: 'building_safety',
    label: 'Building Safety',
    icon: Shield,
    endpoint: '/inspection/building-safety',
    desc: 'EfficientNet — Safe / Minor / Moderate / Severe Damage',
    color: 'bg-green-50 border-green-200 text-green-800',
  },
]

const SEVERITY_MAP: Record<string, { icon: string; cls: string }> = {
  none:     { icon: '✅', cls: 'bg-green-100 text-green-800' },
  low:      { icon: '🟡', cls: 'bg-yellow-100 text-yellow-800' },
  moderate: { icon: '🟠', cls: 'bg-orange-100 text-orange-800' },
  high:     { icon: '🔴', cls: 'bg-red-100 text-red-800' },
  critical: { icon: '🚨', cls: 'bg-red-200 text-red-900 font-bold' },
}

function SeverityBadge({ severity }: { severity: string }) {
  const s = SEVERITY_MAP[severity] ?? SEVERITY_MAP['none']
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${s.cls}`}>
      {s.icon} {capitalize(severity || 'none')}
    </span>
  )
}

function ResultCard({ result }: { result: any }) {
  if (!result) return null

  if (result.status === 'model_weights_not_found') {
    return (
      <Card className="border-orange-200 bg-orange-50">
        <CardContent className="p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-orange-500 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-orange-800">Model Weights Not Loaded</p>
              <p className="text-sm text-orange-700 mt-1">
                To enable AI inspection, export your trained models to{' '}
                <code className="bg-orange-100 px-1 rounded">backend/ml_models/</code>
              </p>
              <p className="text-xs text-orange-600 mt-2">
                See <code>backend/ml_models/README.md</code> for full instructions.
              </p>
            </div>
          </div>
          {result.mock_prediction && (
            <div className="mt-4 p-3 bg-white rounded border border-orange-200">
              <p className="text-xs font-semibold text-orange-700 mb-1">DEMO RESPONSE (no model loaded)</p>
              <p className="text-sm">Classes: {result.classes?.join(', ')}</p>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  const isRoad = result.inspection_type === 'road_damage'

  return (
    <Card className={result.severity === 'critical' || result.severity === 'high' ? 'border-red-300' : 'border-green-200'}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-base">Inspection Result</CardTitle>
          <SeverityBadge severity={result.severity ?? 'none'} />
        </div>
        <p className="text-xs text-muted-foreground mt-1">Model: {result.model_name}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Scores */}
        <div className="grid grid-cols-2 gap-3">
          {!isRoad && (
            <div className="bg-muted/50 rounded-lg p-3">
              <p className="text-xs text-muted-foreground">Prediction</p>
              <p className="text-sm font-bold mt-1">{result.predicted_class ?? '—'}</p>
            </div>
          )}
          {result.confidence !== undefined && (
            <div className="bg-muted/50 rounded-lg p-3">
              <p className="text-xs text-muted-foreground">Confidence</p>
              <p className="text-lg font-bold mt-1">{(result.confidence * 100).toFixed(1)}%</p>
            </div>
          )}
          <div className="bg-muted/50 rounded-lg p-3">
            <p className="text-xs text-muted-foreground">Severity Score</p>
            <p className="text-lg font-bold mt-1">{result.severity_score?.toFixed(1) ?? '0'}<span className="text-xs text-muted-foreground">/100</span></p>
          </div>
          {isRoad && (
            <div className="bg-muted/50 rounded-lg p-3">
              <p className="text-xs text-muted-foreground">Defects Found</p>
              <p className="text-lg font-bold mt-1">{result.total_defects ?? 0}</p>
            </div>
          )}
        </div>

        {/* Road detections */}
        {isRoad && result.detections?.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">Detected Defects</p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {result.detections.map((d: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-sm bg-red-50 rounded px-3 py-1.5">
                  <span className="font-medium capitalize">{d.class}</span>
                  <span className="text-muted-foreground">{(d.confidence * 100).toFixed(1)}% conf</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Class probabilities bar chart */}
        {result.class_probabilities && (
          <div>
            <p className="text-sm font-medium mb-2">Class Probabilities</p>
            <div className="space-y-2">
              {Object.entries(result.class_probabilities).map(([cls, prob]: any) => (
                <div key={cls} className="flex items-center gap-2">
                  <span className="text-xs w-36 truncate text-muted-foreground">{cls}</span>
                  <div className="flex-1 bg-muted rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min((prob * 100), 100)}%` }}
                    />
                  </div>
                  <span className="text-xs w-10 text-right font-medium">{(prob * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommendation */}
        {result.recommendation && (
          <div className={`rounded-lg p-4 border ${
            result.repair_urgency === 'immediate'
              ? 'bg-red-50 border-red-200'
              : result.repair_urgency === 'soon'
              ? 'bg-yellow-50 border-yellow-200'
              : 'bg-blue-50 border-blue-200'
          }`}>
            <p className="text-xs font-semibold uppercase tracking-wide mb-1.5">
              {result.repair_urgency === 'immediate' ? '🚨 Immediate Action Required'
                : result.repair_urgency === 'soon' ? '⚠️ Action Recommended Soon'
                : '📋 Recommendation'}
            </p>
            <p className="text-sm">{result.recommendation}</p>
          </div>
        )}

        {/* Repair cost */}
        {(result.estimated_repair_cost_min > 0 || result.estimated_repair_cost_max > 0) && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-amber-800 mb-1">Estimated Repair Cost (INR)</p>
            <p className="text-xl font-bold text-amber-900">
              {result.estimated_repair_cost_min?.toLocaleString()} —{' '}
              {result.estimated_repair_cost_max?.toLocaleString()}
            </p>
            <p className="text-xs text-amber-600 mt-1">Indicative range. Obtain professional quote.</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function HistoryTable({ history }: { history: any[] }) {
  if (!history?.length) {
    return (
      <div className="text-center py-16">
        <Clock className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
        <p className="text-muted-foreground">No inspection history yet.</p>
        <p className="text-sm text-muted-foreground/60 mt-1">Upload an image to run your first inspection.</p>
      </div>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            {['Type', 'Prediction', 'Confidence', 'Severity', 'Urgency', 'Date', 'Verified'].map(h => (
              <th key={h} className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {history.map((ins: any) => (
            <tr key={ins.id} className="hover:bg-muted/30">
              <td className="px-3 py-2">
                <Badge variant="outline" className="text-xs">{capitalize(ins.inspection_type)}</Badge>
              </td>
              <td className="px-3 py-2 font-medium">{ins.predicted_class ?? '—'}</td>
              <td className="px-3 py-2">{ins.confidence ? `${(ins.confidence * 100).toFixed(1)}%` : '—'}</td>
              <td className="px-3 py-2"><SeverityBadge severity={ins.severity} /></td>
              <td className="px-3 py-2 text-xs capitalize">{ins.repair_urgency ?? '—'}</td>
              <td className="px-3 py-2 text-xs text-muted-foreground">{formatDate(ins.created_at)}</td>
              <td className="px-3 py-2">
                {ins.is_verified
                  ? <CheckCircle2 className="h-4 w-4 text-green-500" />
                  : <span className="text-xs text-muted-foreground">No</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function InspectionPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [activeType, setActiveType] = useState(INSPECTION_TYPES[0])
  const [projectId, setProjectId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [tab, setTab] = useState<'inspect' | 'history'>('inspect')

  // Cleanup blob URL on unmount / file change
  useEffect(() => {
    return () => { if (preview) URL.revokeObjectURL(preview) }
  }, [preview])

  const { data: projects } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data),
  })

  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ['inspection-history'],
    queryFn: () => api.get('/inspection/history').then(r => r.data),
  })

  const { data: stats } = useQuery({
    queryKey: ['inspection-stats'],
    queryFn: () => api.get('/inspection/stats').then(r => r.data),
  })

  const uploadMut = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('No file selected')
      const fd = new FormData()
      fd.append('file', file)
      if (projectId && projectId !== 'none') fd.append('project_id', projectId)
      return api.post(activeType.endpoint, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: ({ data }) => {
      setResult(data)
      refetchHistory()
      toast.success('Inspection complete!')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Inspection failed'),
  })

  const handleFile = (f: File | null) => {
    if (preview) URL.revokeObjectURL(preview)
    setFile(f)
    setResult(null)
    setPreview(f ? URL.createObjectURL(f) : null)
  }

  return (
    <div className="space-y-5">
      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {[
          { id: 'inspect', label: 'New Inspection', icon: Eye },
          { id: 'history', label: `History (${history?.length ?? 0})`, icon: History },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as any)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <t.icon className="h-4 w-4" />{t.label}
          </button>
        ))}
      </div>

      {tab === 'inspect' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left panel */}
          <div className="space-y-4">
            {/* Stats row */}
            {stats && (
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Total', value: stats.total_inspections, color: '' },
                  { label: 'Critical', value: stats.critical_count, color: 'text-red-600' },
                  { label: 'High Risk', value: stats.high_count, color: 'text-orange-600' },
                ].map(s => (
                  <Card key={s.label}>
                    <CardContent className="p-3 text-center">
                      <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                      <p className="text-xs text-muted-foreground">{s.label}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Model selector */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Eye className="h-5 w-5" /> Select Inspection Type
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  {INSPECTION_TYPES.map(t => {
                    const Icon = t.icon
                    const active = activeType.value === t.value
                    return (
                      <button
                        key={t.value}
                        onClick={() => { setActiveType(t); setResult(null) }}
                        className={`p-3 rounded-lg border-2 text-left transition-all ${
                          active ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'
                        }`}
                      >
                        <Icon className={`h-5 w-5 mb-1.5 ${active ? 'text-primary' : 'text-muted-foreground'}`} />
                        <p className="text-xs font-semibold leading-tight">{t.label}</p>
                        <p className="text-xs text-muted-foreground mt-0.5 leading-tight line-clamp-2">{t.desc}</p>
                      </button>
                    )
                  })}
                </div>

                {/* Optional project link */}
                <div className="space-y-1.5">
                  <Label className="text-xs">Link to Project (optional)</Label>
                  <Select value={projectId} onValueChange={setProjectId}>
                    <SelectTrigger><SelectValue placeholder="No project" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No project</SelectItem>
                      {(projects ?? []).map((p: any) => (
                        <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Image upload drop zone */}
                <div
                  className="border-2 border-dashed border-muted-foreground/30 rounded-lg overflow-hidden cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => fileRef.current?.click()}
                >
                  {preview ? (
                    <div className="relative">
                      <img src={preview} alt="preview" className="w-full h-48 object-cover" />
                      <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                        <p className="text-white text-sm font-medium">Click to change image</p>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center">
                      <Upload className="h-10 w-10 text-muted-foreground/40 mx-auto mb-2" />
                      <p className="text-sm font-medium">Click to upload image</p>
                      <p className="text-xs text-muted-foreground mt-1">JPG, PNG, WEBP · Max 50MB</p>
                    </div>
                  )}
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/bmp"
                    className="hidden"
                    onChange={e => handleFile(e.target.files?.[0] ?? null)}
                  />
                </div>

                {file && (
                  <p className="text-xs text-muted-foreground">
                    Selected: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
                  </p>
                )}

                <Button
                  onClick={() => uploadMut.mutate()}
                  disabled={!file || uploadMut.isPending}
                  className="w-full gap-2"
                >
                  {uploadMut.isPending
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Analysing…</>
                    : <><Eye className="h-4 w-4" /> Run {activeType.label}</>
                  }
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Right panel — result */}
          <div>
            {result ? (
              <ResultCard result={result} />
            ) : (
              <Card className="h-full flex items-center justify-center min-h-[450px]">
                <CardContent className="text-center py-16">
                  <Eye className="h-14 w-14 text-muted-foreground/20 mx-auto mb-4" />
                  <p className="font-medium text-muted-foreground">Upload an image to run AI inspection</p>
                  <p className="text-sm text-muted-foreground/60 mt-1">
                    Detects cracks, structural damage, road defects, and safety issues
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <HistoryTable history={history ?? []} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
