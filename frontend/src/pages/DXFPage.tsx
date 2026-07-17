import { useState, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Upload, FileText, AlertCircle, CheckCircle2, Loader2, Info } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { formatNumber } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

export default function DXFPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [projectId, setProjectId] = useState('')
  const [units, setUnits] = useState('mm')
  const [applyToBuilding, setApplyToBuilding] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)

  const { data: projects } = useQuery({ queryKey: ['projects-list'], queryFn: () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data) })

  const uploadMut = useMutation({
    mutationFn: async () => {
      if (!file || !projectId) throw new Error('Select project and file')
      const fd = new FormData()
      fd.append('file', file)
      fd.append('units', units)
      fd.append('apply_to_building', String(applyToBuilding))
      return api.post(`/dxf/upload/${projectId}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    onSuccess: ({ data }) => { setResult(data); toast.success('DXF parsed successfully') },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Upload failed'),
  })

  const { data: guide } = useQuery({ queryKey: ['dxf-guide'], queryFn: () => api.get('/dxf/layers-guide').then(r => r.data) })

  const extracted = result?.extracted

  return (
    <div className="space-y-5">
      {/* Upload Card */}
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5" /> Upload DXF Drawing</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1.5 col-span-2">
              <Label>Project *</Label>
              <Select onValueChange={setProjectId}>
                <SelectTrigger><SelectValue placeholder="Select project..." /></SelectTrigger>
                <SelectContent>{(projects ?? []).map((p: any) => <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Drawing Units</Label>
              <Select defaultValue="mm" onValueChange={setUnits}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {['mm','cm','m','ft','in'].map(u => <SelectItem key={u} value={u}>{u.toUpperCase()}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Apply to Building?</Label>
              <Select defaultValue="false" onValueChange={v => setApplyToBuilding(v === 'true')}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="false">Extract Only</SelectItem>
                  <SelectItem value="true">Extract & Apply</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

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
            <input ref={fileRef} type="file" accept=".dxf" className="hidden" onChange={e => setFile(e.target.files?.[0] ?? null)} />
          </div>

          <Button onClick={() => uploadMut.mutate()} disabled={!file || !projectId || uploadMut.isPending} className="w-full">
            {uploadMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
            {uploadMut.isPending ? 'Parsing DXF...' : 'Upload & Parse'}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      {extracted && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-700">
              <CheckCircle2 className="h-5 w-5" /> Extraction Results — {result.filename}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
              {[
                { label: 'Total Wall Length', value: formatNumber(extracted.total_wall_length_m, 2), unit: 'm' },
                { label: 'Total Floor Area', value: formatNumber(extracted.total_floor_area_m2, 2), unit: 'm²' },
                { label: 'Doors Detected', value: extracted.num_doors, unit: 'nos' },
                { label: 'Windows Detected', value: extracted.num_windows, unit: 'nos' },
              ].map(({ label, value, unit }) => (
                <div key={label} className="bg-muted/50 rounded-lg p-4 text-center">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-2xl font-bold mt-1">{value}</p>
                  <p className="text-xs text-muted-foreground">{unit}</p>
                </div>
              ))}
            </div>
            {extracted.rooms?.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">Detected Rooms ({extracted.rooms.length})</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {extracted.rooms.map((r: any, i: number) => (
                    <div key={i} className="bg-blue-50 rounded p-2 text-xs">
                      <p className="font-medium">{r.name}</p>
                      <p className="text-muted-foreground">{formatNumber(r.area_m2, 2)} m²</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {result.warnings?.length > 0 && (
              <div className="mt-4 space-y-2">
                {result.warnings.map((w: string, i: number) => (
                  <div key={i} className="flex gap-2 bg-yellow-50 border border-yellow-200 rounded p-3 text-sm text-yellow-800">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />{w}
                  </div>
                ))}
              </div>
            )}
            {result.applied_to_building && (
              <div className="mt-3 flex gap-2 bg-green-50 border border-green-200 rounded p-3 text-sm text-green-700">
                <CheckCircle2 className="h-4 w-4 shrink-0" /> Dimensions applied to project building. Run estimation to calculate quantities.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Guide */}
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Info className="h-4 w-4" /> DXF Layer Naming Guide</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
            {guide && Object.entries(guide).filter(([k]) => k.endsWith('_layers')).map(([key, vals]: any) => (
              <div key={key}>
                <p className="font-medium capitalize mb-1">{key.replace('_layers','').replace('_',' ')}</p>
                <div className="flex flex-wrap gap-1">
                  {vals.map((v: string) => <Badge key={v} variant="outline" className="text-xs">{v}</Badge>)}
                </div>
              </div>
            ))}
          </div>
          {guide?.tips && (
            <ul className="mt-4 space-y-1">
              {guide.tips.map((t: string, i: number) => <li key={i} className="text-xs text-muted-foreground flex gap-2"><span className="text-primary">•</span>{t}</li>)}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
