import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import ProtectedRoute from '@/components/layout/ProtectedRoute'
import AppLayout from '@/components/layout/AppLayout'
import { ToastProvider, ToastViewport } from '@/components/ui/toast'

const LoginPage          = lazy(() => import('@/pages/auth/LoginPage'))
const RegisterPage       = lazy(() => import('@/pages/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'))
const DashboardPage      = lazy(() => import('@/pages/DashboardPage'))
const ProjectsPage       = lazy(() => import('@/pages/ProjectsPage'))
const BuildingsPage      = lazy(() => import('@/pages/BuildingsPage'))
const EstimationPage     = lazy(() => import('@/pages/EstimationPage'))
const MaterialsPage      = lazy(() => import('@/pages/MaterialsPage'))
const BOQPage            = lazy(() => import('@/pages/BOQPage'))
const AnalyticsPage      = lazy(() => import('@/pages/AnalyticsPage'))
const DXFPage            = lazy(() => import('@/pages/DXFPage'))
const InspectionPage     = lazy(() => import('@/pages/InspectionPage'))
const ProfilePage        = lazy(() => import('@/pages/ProfilePage'))

function Loader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-full border-4 border-primary border-t-transparent animate-spin" />
        <p className="text-sm text-muted-foreground">SmartBOQ Pro…</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider swipeDirection="right">
          <Suspense fallback={<Loader />}>
            <Routes>
              {/* Public */}
              <Route path="/login"           element={<LoginPage />} />
              <Route path="/register"        element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />

              {/* Redirect root → dashboard */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* Protected */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route path="/dashboard"  element={<DashboardPage />} />
                  <Route path="/projects"   element={<ProjectsPage />} />
                  <Route path="/buildings"  element={<BuildingsPage />} />
                  <Route path="/estimation" element={<EstimationPage />} />
                  <Route path="/materials"  element={<MaterialsPage />} />
                  <Route path="/boq"        element={<BOQPage />} />
                  <Route path="/analytics"  element={<AnalyticsPage />} />
                  <Route path="/dxf"        element={<DXFPage />} />
                  <Route path="/inspection" element={<InspectionPage />} />
                  <Route path="/profile"    element={<ProfilePage />} />
                  {/* Catch-all → dashboard */}
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
          <ToastViewport />
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
