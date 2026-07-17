import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { User, Lock, Building2, Phone, Loader2, CheckCircle2 } from 'lucide-react'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { capitalize } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

const profileSchema = z.object({
  full_name:   z.string().min(2, 'Name required'),
  phone:       z.string().optional(),
  company:     z.string().optional(),
  designation: z.string().optional(),
})

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Required'),
  new_password: z.string()
    .min(8, 'Min 8 characters')
    .regex(/[A-Z]/, 'Must contain uppercase')
    .regex(/[0-9]/, 'Must contain digit'),
  confirm_password: z.string(),
}).refine(d => d.new_password === d.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
})

type ProfileForm = z.infer<typeof profileSchema>
type PasswordForm = z.infer<typeof passwordSchema>

export default function ProfilePage() {
  const { user, updateUser } = useAuth()
  const [pwdSuccess, setPwdSuccess] = useState(false)

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name:   user?.full_name ?? '',
      phone:       user?.phone ?? '',
      company:     user?.company ?? '',
      designation: user?.designation ?? '',
    },
  })

  const passwordForm = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
  })

  const profileMut = useMutation({
    mutationFn: (data: ProfileForm) => api.put('/users/me', data),
    onSuccess: ({ data }) => { updateUser(data); toast.success('Profile updated!') },
    onError: () => toast.error('Failed to update profile'),
  })

  const passwordMut = useMutation({
    mutationFn: (data: PasswordForm) => api.post('/users/me/change-password', {
      current_password: data.current_password,
      new_password: data.new_password,
    }),
    onSuccess: () => {
      setPwdSuccess(true)
      passwordForm.reset()
      toast.success('Password changed successfully!')
      setTimeout(() => setPwdSuccess(false), 3000)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to change password'),
  })

  const roleColors: Record<string, string> = {
    admin: 'bg-red-100 text-red-800',
    project_manager: 'bg-blue-100 text-blue-800',
    estimation_engineer: 'bg-green-100 text-green-800',
    quantity_surveyor: 'bg-purple-100 text-purple-800',
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Avatar + role */}
      <Card>
        <CardContent className="p-6 flex items-center gap-5">
          <div className="h-16 w-16 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-2xl font-bold shrink-0">
            {user?.full_name?.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-bold">{user?.full_name}</h2>
            <p className="text-muted-foreground text-sm">{user?.email}</p>
            <span className={`mt-1 inline-block text-xs px-2 py-0.5 rounded-full font-medium ${roleColors[user?.role ?? ''] ?? 'bg-gray-100 text-gray-800'}`}>
              {capitalize(user?.role ?? '')}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Edit profile */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <User className="h-4 w-4" /> Edit Profile
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={profileForm.handleSubmit(d => profileMut.mutate(d))} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-1.5">
                <Label>Full Name</Label>
                <Input {...profileForm.register('full_name')} />
                {profileForm.formState.errors.full_name && (
                  <p className="text-xs text-destructive">{profileForm.formState.errors.full_name.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>Phone</Label>
                <Input {...profileForm.register('phone')} placeholder="+92-300-0000000" />
              </div>
              <div className="space-y-1.5">
                <Label>Company</Label>
                <Input {...profileForm.register('company')} placeholder="ABC Construction" />
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label>Designation</Label>
                <Input {...profileForm.register('designation')} placeholder="Senior Estimation Engineer" />
              </div>
            </div>
            <Button
              type="submit"
              disabled={profileMut.isPending}
            >
              {profileMut.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Save Profile
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Change password */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Lock className="h-4 w-4" /> Change Password
          </CardTitle>
        </CardHeader>
        <CardContent>
          {pwdSuccess ? (
            <div className="flex items-center gap-3 text-green-700 bg-green-50 rounded-lg p-4">
              <CheckCircle2 className="h-5 w-5" />
              <p className="font-medium">Password changed successfully!</p>
            </div>
          ) : (
            <form onSubmit={passwordForm.handleSubmit(d => passwordMut.mutate(d))} className="space-y-4">
              <div className="space-y-1.5">
                <Label>Current Password</Label>
                <Input type="password" {...passwordForm.register('current_password')} />
                {passwordForm.formState.errors.current_password && (
                  <p className="text-xs text-destructive">{passwordForm.formState.errors.current_password.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>New Password</Label>
                <Input type="password" {...passwordForm.register('new_password')} />
                {passwordForm.formState.errors.new_password && (
                  <p className="text-xs text-destructive">{passwordForm.formState.errors.new_password.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>Confirm New Password</Label>
                <Input type="password" {...passwordForm.register('confirm_password')} />
                {passwordForm.formState.errors.confirm_password && (
                  <p className="text-xs text-destructive">{passwordForm.formState.errors.confirm_password.message}</p>
                )}
              </div>
              <Button type="submit" disabled={passwordMut.isPending}>
                {passwordMut.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                Change Password
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
