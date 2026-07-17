import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { HardHat, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const schema = z.object({
  full_name: z.string().min(2, 'Name required'),
  email: z.string().email('Invalid email'),
  password: z.string().min(8).regex(/[A-Z]/, 'Needs uppercase').regex(/[0-9]/, 'Needs digit'),
  role: z.enum(['estimation_engineer', 'quantity_surveyor', 'project_manager']),
  company: z.string().optional(),
  designation: z.string().optional(),
})
type FormData = z.infer<typeof schema>

export default function RegisterPage() {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'estimation_engineer' },
  })

  const onSubmit = async (data: FormData) => {
    setError('')
    try {
      await api.post('/auth/register', data)
      navigate('/login', { state: { message: 'Account created! Please sign in.' } })
    } catch (e: any) {
      const detail = e.response?.data?.detail
      if (Array.isArray(detail)) {
        // Pydantic validation errors — show all messages
        setError(detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('. '))
      } else if (typeof detail === 'string') {
        setError(detail)
      } else if (e.code === 'ERR_NETWORK' || !e.response) {
        setError('Cannot connect to server. Make sure the backend is running on port 8000.')
      } else {
        setError(`Registration failed (HTTP ${e.response?.status}). Please try again.`)
      }
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--secondary))] flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-white/20 backdrop-blur mb-3">
            <HardHat className="h-7 w-7 text-amber-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Create Account</h1>
          <p className="text-white/70 text-sm">SmartBOQ Pro — Professional Edition</p>
        </div>
        <Card className="shadow-2xl">
          <CardHeader><CardTitle className="text-center">Register</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {error && <div className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive">{error}</div>}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5 col-span-2">
                  <Label>Full Name</Label>
                  <Input placeholder="Ali Hassan" {...register('full_name')} />
                  {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
                </div>
                <div className="space-y-1.5 col-span-2">
                  <Label>Email</Label>
                  <Input type="email" placeholder="ali@company.com" {...register('email')} />
                  {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                </div>
                <div className="space-y-1.5 col-span-2">
                  <Label>Password</Label>
                  <Input type="password" placeholder="Min 8 chars, 1 uppercase (A-Z), 1 digit (0-9)" {...register('password')} />
                  {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                  <p className="text-xs text-muted-foreground">Example: MyPass123</p>
                </div>
                <div className="space-y-1.5 col-span-2">
                  <Label>Role</Label>
                  <Select defaultValue="estimation_engineer" onValueChange={v => setValue('role', v as any)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="estimation_engineer">Estimation Engineer</SelectItem>
                      <SelectItem value="quantity_surveyor">Quantity Surveyor</SelectItem>
                      <SelectItem value="project_manager">Project Manager</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Company (optional)</Label>
                  <Input placeholder="ABC Construction" {...register('company')} />
                </div>
                <div className="space-y-1.5">
                  <Label>Designation (optional)</Label>
                  <Input placeholder="Senior QS" {...register('designation')} />
                </div>
              </div>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                {isSubmitting ? 'Creating…' : 'Create Account'}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
