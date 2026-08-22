import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Search, Pencil, Archive, Trash2, Eye, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatCurrency, formatDate, capitalize, statusColor } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

const schema = z.object({
  project_name: z.string().min(2, 'Required'),
  client_name: z.string().min(2, 'Required'),
  location: z.string().min(2, 'Required'),
  building_type: z.string().default('residential'),
  num_floors: z.coerce.number().min(1).max(200),
  status: z.string().default('draft'),
  description: z.string().optional(),
  city: z.string().optional(),
  country: z.string().default('India'),
  currency: z.string().default('INR'),
})
type FormData = z.infer<typeof schema>

function ProjectFormModal({ open, onClose, existing }: { open: boolean; onClose: () => void; existing?: any }) {
  const qc = useQueryClient()
  const { register, handleSubmit, control, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: existing ?? {
      building_type: 'residential',
      num_floors: 1,
      status: 'draft',
      country: 'India',
      currency: 'INR',
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      existing ? api.put(`/projects/${existing.id}`, data) : api.post('/projects/', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      toast.success(existing ? 'Project updated!' : 'Project created!')
      onClose()
      reset()
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to save project'),
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <CardHeader>
          <CardTitle>{existing ? 'Edit Project' : 'New Project'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(d => mutation.mutate(d))} className="grid grid-cols-2 gap-4">
            {/* Project Name */}
            <div className="col-span-2 space-y-1.5">
              <Label>Project Name *</Label>
              <Input {...register('project_name')} placeholder="G+3 Residential Villa, DHA Lahore" />
              {errors.project_name && <p className="text-xs text-destructive">{errors.project_name.message}</p>}
            </div>

            {/* Client Name */}
            <div className="space-y-1.5">
              <Label>Client Name *</Label>
              <Input {...register('client_name')} placeholder="Mr. Ahmed Khan" />
              {errors.client_name && <p className="text-xs text-destructive">{errors.client_name.message}</p>}
            </div>

            {/* Location */}
            <div className="space-y-1.5">
              <Label>Location *</Label>
              <Input {...register('location')} placeholder="DHA Phase 5, Lahore" />
              {errors.location && <p className="text-xs text-destructive">{errors.location.message}</p>}
            </div>

            {/* Building Type — controlled Select */}
            <div className="space-y-1.5">
              <Label>Building Type *</Label>
              <Controller
                name="building_type"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="residential">Residential</SelectItem>
                      <SelectItem value="commercial">Commercial</SelectItem>
                      <SelectItem value="industrial">Industrial</SelectItem>
                      <SelectItem value="institutional">Institutional</SelectItem>
                      <SelectItem value="mixed_use">Mixed Use</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>

            {/* Status — controlled Select */}
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Controller
                name="status"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="on_hold">On Hold</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>

            {/* No. of Floors */}
            <div className="space-y-1.5">
              <Label>No. of Floors *</Label>
              <Input type="number" min={1} max={200} {...register('num_floors')} />
              {errors.num_floors && <p className="text-xs text-destructive">{errors.num_floors.message}</p>}
            </div>

            {/* City */}
            <div className="space-y-1.5">
              <Label>City</Label>
              <Input {...register('city')} placeholder="Lahore" />
            </div>

            {/* Description */}
            <div className="col-span-2 space-y-1.5">
              <Label>Description</Label>
              <Input {...register('description')} placeholder="Brief project description..." />
            </div>

            <div className="col-span-2 flex gap-3 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting || mutation.isPending}>
                {(isSubmitting || mutation.isPending) && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                {existing ? 'Save Changes' : 'Create Project'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['projects', search, statusFilter],
    queryFn: () => api.get('/projects/', {
      params: {
        search: search || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit: 100,
      },
    }).then(r => r.data),
  })

  const archiveMut = useMutation({
    mutationFn: (id: string) => api.post(`/projects/${id}/archive`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project archived') },
    onError: () => toast.error('Failed to archive'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/projects/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project deleted') },
    onError: () => toast.error('Failed to delete'),
  })

  const projects = data?.data ?? []

  return (
    <div className="space-y-5">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-3 flex-1 max-w-xl">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search by name, client, code..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="on_hold">On Hold</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => { setEditing(null); setShowForm(true) }}>
          <Plus className="h-4 w-4 mr-2" /> New Project
        </Button>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
      ) : projects.length === 0 ? (
        <Card>
          <CardContent className="py-20 text-center">
            <p className="text-muted-foreground text-lg">No projects found.</p>
            <Button className="mt-4" onClick={() => { setEditing(null); setShowForm(true) }}>
              <Plus className="h-4 w-4 mr-2" /> Create First Project
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                {['Code', 'Project Name', 'Client', 'Location', 'Type', 'Floors', 'Est. Cost', 'Status', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left font-medium text-xs">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {projects.map((p: any) => (
                <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{p.project_code}</td>
                  <td className="px-4 py-3 font-medium">{p.project_name}</td>
                  <td className="px-4 py-3">{p.client_name}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs max-w-[120px] truncate">{p.location}</td>
                  <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{capitalize(p.building_type)}</Badge></td>
                  <td className="px-4 py-3 text-center">{p.num_floors}</td>
                  <td className="px-4 py-3 font-medium">{formatCurrency(p.total_estimated_cost ?? 0)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColor(p.status)}`}>
                      {capitalize(p.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" title="View" onClick={() => navigate(`/projects/${p.id}`)}>
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Edit" onClick={() => { setEditing(p); setShowForm(true) }}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Archive" onClick={() => archiveMut.mutate(p.id)}>
                        <Archive className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost" size="icon"
                        className="text-destructive hover:text-destructive"
                        title="Delete"
                        onClick={() => { if (confirm(`Delete "${p.project_name}"?`)) deleteMut.mutate(p.id) }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 text-xs text-muted-foreground border-t bg-muted/20">
            Showing {projects.length} of {data?.total ?? 0} projects
          </div>
        </div>
      )}

      <ProjectFormModal
        open={showForm}
        onClose={() => { setShowForm(false); setEditing(null) }}
        existing={editing}
      />
    </div>
  )
}
