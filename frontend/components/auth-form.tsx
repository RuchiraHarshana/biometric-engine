"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import { AlertCircle, Loader2, Lock } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import { setStoredUser, generateUserId } from "@/lib/auth"

const signInSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  rememberMe: z.boolean().default(false),
})

const registerSchema = z
  .object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.string().email("Invalid email address"),
    password: z.string().min(6, "Password must be at least 6 characters"),
    confirmPassword: z.string().min(6, "Password must be at least 6 characters"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  })

type SignInInput = z.infer<typeof signInSchema>
type RegisterInput = z.infer<typeof registerSchema>

export function AuthForm() {
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const signInForm = useForm<SignInInput>({
    resolver: zodResolver(signInSchema),
    defaultValues: {
      email: "",
      password: "",
      rememberMe: false,
    },
  })

  const registerForm = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  })

  const handleSignIn = async (data: SignInInput) => {
    try {
      setError(null)
      const user = {
        id: generateUserId(),
        email: data.email,
        name: "User",
      }
      setStoredUser(user)
      router.push("/dashboard")
    } catch (err) {
      setError("Failed to sign in. Please try again.")
    }
  }

  const handleRegister = async (data: RegisterInput) => {
    try {
      setError(null)
      const user = {
        id: generateUserId(),
        email: data.email,
        name: data.name,
      }
      setStoredUser(user)
      router.push("/dashboard")
    } catch (err) {
      setError("Failed to register. Please try again.")
    }
  }

  return (
    <Card className="w-full max-w-md bg-card/50 border-border">
      <div className="p-8">
        <div className="flex items-center justify-center mb-8">
          <div className="w-10 h-10 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
            <Lock className="w-6 h-6 text-accent" />
          </div>
        </div>

        <Tabs defaultValue="signin" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="signin">Sign In</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>

          {/* Sign In Tab */}
          <TabsContent value="signin" className="space-y-6">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={signInForm.handleSubmit(handleSignIn)} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Email</label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  {...signInForm.register("email")}
                  className="bg-input border-border"
                />
                {signInForm.formState.errors.email && (
                  <p className="text-xs text-destructive">{signInForm.formState.errors.email.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <Input
                  type="password"
                  placeholder="••••••"
                  {...signInForm.register("password")}
                  className="bg-input border-border"
                />
                {signInForm.formState.errors.password && (
                  <p className="text-xs text-destructive">{signInForm.formState.errors.password.message}</p>
                )}
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox {...signInForm.register("rememberMe")} />
                  <span>Remember me</span>
                </label>
                <a href="#" className="text-xs text-accent hover:underline">
                  Forgot password?
                </a>
              </div>

              <Button type="submit" className="w-full" disabled={signInForm.formState.isSubmitting}>
                {signInForm.formState.isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  "Continue"
                )}
              </Button>
            </form>
          </TabsContent>

          {/* Register Tab */}
          <TabsContent value="register" className="space-y-6">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={registerForm.handleSubmit(handleRegister)} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Full Name</label>
                <Input
                  type="text"
                  placeholder="John Doe"
                  {...registerForm.register("name")}
                  className="bg-input border-border"
                />
                {registerForm.formState.errors.name && (
                  <p className="text-xs text-destructive">{registerForm.formState.errors.name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Email</label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  {...registerForm.register("email")}
                  className="bg-input border-border"
                />
                {registerForm.formState.errors.email && (
                  <p className="text-xs text-destructive">{registerForm.formState.errors.email.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <Input
                  type="password"
                  placeholder="••••••"
                  {...registerForm.register("password")}
                  className="bg-input border-border"
                />
                {registerForm.formState.errors.password && (
                  <p className="text-xs text-destructive">{registerForm.formState.errors.password.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Confirm Password</label>
                <Input
                  type="password"
                  placeholder="••••••"
                  {...registerForm.register("confirmPassword")}
                  className="bg-input border-border"
                />
                {registerForm.formState.errors.confirmPassword && (
                  <p className="text-xs text-destructive">{registerForm.formState.errors.confirmPassword.message}</p>
                )}
              </div>

              <Button type="submit" className="w-full" disabled={registerForm.formState.isSubmitting}>
                {registerForm.formState.isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account...
                  </>
                ) : (
                  "Continue"
                )}
              </Button>
            </form>
          </TabsContent>
        </Tabs>
      </div>
    </Card>
  )
}
