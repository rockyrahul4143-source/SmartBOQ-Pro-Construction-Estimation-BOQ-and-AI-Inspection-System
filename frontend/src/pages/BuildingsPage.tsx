import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Plus, Building2, Loader2, Save } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/hooks/useToast'

const DEFAULT_VALUES = {
  building_name: 'Main Building',
  num_floors: 1,
  plot_length: 0, plot_width: 0, excavation_depth: 1.5,
  footing_length: 1.2, footing_width: 1.2, footing_depth: 0.3, num_footings: 0,
  pcc_thickness: 0.075,
  column_length: 0.3, column_width: 0.3, floor_height: 3.0, num_columns: 0,
  beam_width: 0.23, beam_depth: 0.45, total_beam_length: 0,
  slab_length: 0, slab_width: 0, slab_thickness: 0.125,
  wall_thickness_external: 0.23, wall_thickness_internal: 0.115,
  total_external_wall_length: 0, total_internal_wall_length: 0, wall_height: 3.0,
  plaster_thickness_external: 0.020, plaster_thickness_internal: 0.012,
  num_doors: 0, door_width: 0.9, door_height: 2.1,
  num_windows: 0, window_width: 1.2, window_height: 1.2,
  steel_percentage_slab: 1.0, steel_percentage_column: 2.5, steel_percentage_beam: 2.0,
  waterproofing_area: 0, tile_wastage_pct: 10, paint_coats: 2,
}

function Field({ label, name, register, type = 'number', step = '0.001' }: any) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        type={type}
        step={step}
        className="h-8 text-sm"
        {...register(name, { valueAsNumber: type === 'number' })}
      />
    </div>
  )
}

const SECTIONS = [
  {
    title: 'General', icon: '🏗️', fields: [
      { label: 'Building Name', name: 'building_name', type: 'text', step: undefined },
      { label: 'No. of Floors', name: 'num_floors', step: '1' },
    ],
  },
  {
    title: 'Plot & Foundation (m)', icon: '📐', fields: [
      { label: 'Plot Length', name: 'plot_length' },
      { label: 'Plot Width', name: 'plot_width' },
      { label: 'Excavation Depth', name: 'excavation_depth' },
      { label: 'PCC Thickness', name: 'pcc_thickness' },
    ],
  },
  {
    title: 'Footings (m)', icon: '⬛', fields: [
      { label: 'Footing Length', name: 'footing_length' },
      { label: 'Footing Width', name: 'footing_width' },
      { label: 'Footing Depth', name: 'footing_depth' },
      { label: 'No. of Footings', name: 'num_footings', step: '1' },
    ],
  },
  {
    title: 'Columns & Beams (m)', icon: '🔲', fields: [
      { label: 'Col. Length', name: 'column_length' },
      { label: 'Col. Width', name: 'column_width' },
      { label: 'Floor Height', name: 'floor_height' },
      { label: 'No. of Columns', name: 'num_columns', step: '1' },
      { label: 'Beam Width', name: 'beam_width' },
      { label: 'Beam Depth', name: 'beam_depth' },
      { label: 'Total Beam Length', name: 'total_beam_length' },
    ],
  },
  {
    title: 'Slab (m)', icon: '▭', fields: [
      { label: 'Slab Length', name: 'slab_length' },
      { label: 'Slab Width', name: 'slab_width' },
      { label: 'Slab Thickness', name: 'slab_thickness' },
    ],
  },
  {
    title: 'Walls (m)', icon: '🧱', fields: [
      { label: 'Ext. Wall Thickness', name: 'wall_thickness_external' },
      { label: 'Int. Wall Thickness', name: 'wall_thickness_internal' },
      { label: 'Total Ext. Wall Length', name: 'total_external_wall_length' },
      { label: 'Total Int. Wall Length', name: 'total_internal_wall_length' },
      { label: 'Wall Height', name: 'wall_height' },
      { label: 'Plaster Ext. Thick (m)', name: 'plaster_thickness_external' },
      { label: 'Plaster Int. Thick (m)', name: 'plaster_thickness_internal' },
    ],
  },
  {
    title: 'Openings', icon: '🚪', fields: [
      { label: 'No. of Doors', name: 'num_doors', step: '1' },
      { label: 'Door Width (m)', name: 'door_width' },
      { label: 'Door Height (m)', name: 'door_height' },
      { label: 'No. of Windows', name: 'num_windows', step: '1' },
      { label: 'Window Width (m)', name: 'window_width' },
      { label: 'Window Height (m)', name: 'window_height' },
    ],
  },
  {
    title: 'Steel & Finishes', icon: '🔩', fields: [
      { label: 'Slab Steel %', name: 'steel_percentage_slab' },
      { label: 'Column Steel %', name: 'steel_percentage_column' },
      { label: 'Beam Steel %', name: 'steel_percentage_beam' },
      { label: 'Waterproofing Area (m²)', name: 'waterproofing_area' },
      { label: 'Tile Wastage %', name: 'tile_wastage_pct' },
      { label: 'Paint Coats', name: 'paint_coats', step: '1' },
    ],
  },
]

export default function BuildingsPage() {
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [selectedBuildingId, setSelectedBuildingId] = useState('')
  const [isNewBuilding, setIsNewBuilding] = useState(false)

  const { register, handleSubmit, reset, formState: { isSubmitting, isDirty } } = useForm({
    defaultValues: DEFAULT_VALUES,
  })

  const { data: projects } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data),
  })

  const { data: buildings, refetch: refetchBuildings } = useQuery({
    queryKey: ['buildings', projectId],
    queryFn: () => api.get(`/buildings/project/${projectId}`).then(r => r.data),
    enabled: !!projectId,
  })

  // ── KEY FIX: Reset form whenever selected building changes ────────
  useEffect(() => {
    if (isNewBuilding) {
      reset(DEFAULT_VALUES)
      return
    }
    if (selectedBuildingId && buildings) {
      const building = buildings.find((b: any) => b.id === selectedBuildingId)
      if (building) {
        // Fill form with ALL existing building values
        reset({
          building_name: building.building_name ?? 'Main Building',
          num_floors: building.num_floors ?? 1,
          plot_length: building.plot_length ?? 0,
          plot_width: building.plot_width ?? 0,
          excavation_depth: building.excavation_depth ?? 1.5,
          footing_length: building.footing_length ?? 1.2,
          footing_width: building.footing_width ?? 1.2,
          footing_depth: building.footing_depth ?? 0.3,
          num_footings: building.num_footings ?? 0,
          pcc_thickness: building.pcc_thickness ?? 0.075,
          column_length: building.column_length ?? 0.3,
          column_width: building.column_width ?? 0.3,
          floor_height: building.floor_height ?? 3.0,
          num_columns: building.num_columns ?? 0,
          beam_width: building.beam_width ?? 0.23,
          beam_depth: building.beam_depth ?? 0.45,
          total_beam_length: building.total_beam_length ?? 0,
          slab_length: building.slab_length ?? 0,
          slab_width: building.slab_width ?? 0,
          slab_thickness: building.slab_thickness ?? 0.125,
          wall_thickness_external: building.wall_thickness_external ?? 0.23,
          wall_thickness_internal: building.wall_thickness_internal ?? 0.115,
          total_external_wall_length: building.total_external_wall_length ?? 0,
          total_internal_wall_length: building.total_internal_wall_length ?? 0,
          wall_height: building.wall_height ?? 3.0,
          plaster_thickness_external: building.plaster_thickness_external ?? 0.020,
          plaster_thickness_internal: building.plaster_thickness_internal ?? 0.012,
          num_doors: building.num_doors ?? 0,
          door_width: building.door_width ?? 0.9,
          door_height: building.door_height ?? 2.1,
          num_windows: building.num_windows ?? 0,
          window_width: building.window_width ?? 1.2,
          window_height: building.window_height ?? 1.2,
          steel_percentage_slab: building.steel_percentage_slab ?? 1.0,
          steel_percentage_column: building.steel_percentage_column ?? 2.5,
          steel_percentage_beam: building.steel_percentage_beam ?? 2.0,
          waterproofing_area: building.waterproofing_area ?? 0,
          tile_wastage_pct: building.tile_wastage_pct ?? 10,
          paint_coats: building.paint_coats ?? 2,
        })
      }
    }
  }, [selectedBuildingId, buildings, isNewBuilding, reset])

  const saveMut = useMutation({
    mutationFn: (data: any) =>
      isNewBuilding || !selectedBuildingId
        ? api.post('/buildings/', { ...data, project_id: projectId })
        : api.put(`/buildings/${selectedBuildingId}`, data),
    onSuccess: ({ data: saved }) => {
      toast.success(isNewBuilding ? 'Building created!' : 'Building updated!')
      refetchBuildings()
      qc.invalidateQueries({ queryKey: ['buildings', projectId] })
      // After creating, switch to the new building
      if (isNewBuilding) {
        setIsNewBuilding(false)
        setSelectedBuildingId(saved.id)
      }
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to save building'),
  })

  const handleProjectChange = (id: string) => {
    setProjectId(id)
    setSelectedBuildingId('')
    setIsNewBuilding(false)
    reset(DEFAULT_VALUES)
  }

  const handleBuildingSelect = (id: string) => {
    setSelectedBuildingId(id)
    setIsNewBuilding(false)
    // reset() is called by useEffect above
  }

  const handleNewBuilding = () => {
    setSelectedBuildingId('')
    setIsNewBuilding(true)
    // reset() is called by useEffect above
  }

  const selectedBuilding = buildings?.find((b: any) => b.id === selectedBuildingId)
  const showForm = !!projectId && (isNewBuilding || !!selectedBuildingId)

  return (
    <div className="space-y-5">
      {/* Project + Building selector */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 items-end">
            {/* Project selector */}
            <div className="space-y-1.5 min-w-[240px]">
              <Label>Project *</Label>
              <Select value={projectId} onValueChange={handleProjectChange}>
                <SelectTrigger><SelectValue placeholder="Select project..." /></SelectTrigger>
                <SelectContent>
                  {(projects ?? []).map((p: any) => (
                    <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Building selector */}
            {projectId && (
              <div className="space-y-1.5 min-w-[200px]">
                <Label>Building</Label>
                <Select
                  value={selectedBuildingId}
                  onValueChange={handleBuildingSelect}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select existing building..." />
                  </SelectTrigger>
                  <SelectContent>
                    {(buildings ?? []).map((b: any) => (
                      <SelectItem key={b.id} value={b.id}>{b.building_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* New building button */}
            {projectId && (
              <Button
                variant={isNewBuilding ? 'default' : 'outline'}
                size="sm"
                onClick={handleNewBuilding}
              >
                <Plus className="h-4 w-4 mr-2" />
                New Building
              </Button>
            )}
          </div>

          {/* Status indicator */}
          {showForm && (
            <div className="mt-3 flex items-center gap-2">
              {isNewBuilding ? (
                <Badge variant="secondary">Creating new building</Badge>
              ) : selectedBuilding ? (
                <Badge variant="outline" className="text-green-700 border-green-300">
                  Editing: {selectedBuilding.building_name}
                </Badge>
              ) : null}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Building form */}
      {showForm && (
        <form onSubmit={handleSubmit(d => saveMut.mutate(d))}>
          <div className="space-y-4">
            {SECTIONS.map(sec => (
              <Card key={sec.title}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <span>{sec.icon}</span>
                    {sec.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {sec.fields.map(f => (
                      <Field
                        key={f.name}
                        label={f.label}
                        name={f.name}
                        register={register}
                        type={(f as any).type ?? 'number'}
                        step={(f as any).step ?? '0.001'}
                      />
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Save button */}
          <div className="mt-5 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {isDirty && !saveMut.isPending ? '⚠ Unsaved changes' : ''}
            </p>
            <Button
              type="submit"
              disabled={isSubmitting || saveMut.isPending}
              className="px-10"
            >
              {(isSubmitting || saveMut.isPending)
                ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> Saving…</>
                : <><Save className="h-4 w-4 mr-2" />{isNewBuilding ? 'Create Building' : 'Update Building'}</>
              }
            </Button>
          </div>
        </form>
      )}

      {/* Empty state */}
      {projectId && !showForm && (
        <Card>
          <CardContent className="py-16 text-center">
            <Building2 className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="font-medium text-muted-foreground">
              {buildings && buildings.length > 0
                ? 'Select a building to edit, or create a new one'
                : 'No buildings yet — click "New Building" to add one'}
            </p>
            <Button className="mt-4" onClick={handleNewBuilding}>
              <Plus className="h-4 w-4 mr-2" /> New Building
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
