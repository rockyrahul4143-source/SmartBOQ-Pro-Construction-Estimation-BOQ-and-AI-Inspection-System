import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { HardHat, Loader2, CheckCircle2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const schema = z.object({ email: z.string().email() })
type F = z.infer<typeof schema>

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<F>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: F) => {
    try { await api.post('/auth/forgot-password', data) } catch {}
    setSent(true)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--secondary))] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-white/20 backdrop-blur mb-3">
            <HardHat className="h-7 w-7 text-amber-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Reset Password</h1>
        </div>
        <Card>
          <CardHeader><CardTitle className="text-center">Forgot Password</CardTitle></CardHeader>
          <CardContent>
            {sent ? (
              <div className="text-center py-6">
                <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-3" />
                <p className="font-medium">Check your email</p>
                <p className="text-sm text-muted-foreground mt-1">If that account exists, we've sent reset instructions.</p>
                <Link to="/login" className="mt-4 inline-block text-sm text-primary hover:underline">Back to Sign In</Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <p className="text-sm text-muted-foreground">Enter your email and we'll send reset instructions.</p>
                <div className="space-y-1.5">
                  <Label>Email Address</Label>
                  <Input type="email" placeholder="you@company.com" {...register('email')} />
                  {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                </div>
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                  Send Reset Link
                </Button>
                <Link to="/login" className="block text-center text-sm text-muted-foreground hover:text-foreground">← Back to Sign In</Link>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
