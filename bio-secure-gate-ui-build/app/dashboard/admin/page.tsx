"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { isAdmin } from "@/lib/auth"
import {
  getOfficers,
  createOfficer,
  updateOfficer,
  deleteOfficer,
  type OfficerOut,
  type CreateOfficerInput,
  type UpdateOfficerInput,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  AlertCircle,
  Plus,
  Trash2,
  Pencil,
  Loader2,
  UserCog,
  X,
  CheckCircle2,
} from "lucide-react"
import { DeleteDialog } from "@/components/delete-dialog"

export default function AdminOfficersPage() {
  const router = useRouter()
  const [officers, setOfficers] = useState<OfficerOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm, setCreateForm] = useState<CreateOfficerInput>({
    email: "",
    password: "",
    full_name: "",
    rank: "",
    id_number: "",
    work_station: "",
    access_type: "verify_only",
  })

  // Edit form
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<UpdateOfficerInput>({})
  const [updating, setUpdating] = useState(false)

  // Delete
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedOfficer, setSelectedOfficer] = useState<OfficerOut | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!isAdmin()) {
      router.replace("/dashboard")
      return
    }
    fetchOfficers()
  }, [router])

  const fetchOfficers = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getOfficers()
      setOfficers(data)
    } catch (err: any) {
      setError(err.message || "Failed to fetch officers")
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!createForm.email || !createForm.password || !createForm.full_name || !createForm.id_number) {
      setError("Email, password, full name, and ID number are required")
      return
    }

    try {
      setCreating(true)
      setError(null)
      await createOfficer(createForm)
      setSuccess("Officer created successfully")
      setShowCreate(false)
      setCreateForm({
        email: "",
        password: "",
        full_name: "",
        rank: "",
        id_number: "",
        work_station: "",
        access_type: "verify_only",
      })
      await fetchOfficers()
    } catch (err: any) {
      setError(err.message || "Failed to create officer")
    } finally {
      setCreating(false)
    }
  }

  const startEdit = (officer: OfficerOut) => {
    setEditingId(officer.user_id)
    setEditForm({
      full_name: officer.full_name,
      rank: officer.rank || "",
      work_station: officer.work_station,
      access_type: officer.access_type,
      is_active: officer.is_active,
    })
  }

  const handleUpdate = async () => {
    if (!editingId) return
    try {
      setUpdating(true)
      setError(null)
      await updateOfficer(editingId, editForm)
      setSuccess("Officer updated successfully")
      setEditingId(null)
      await fetchOfficers()
    } catch (err: any) {
      setError(err.message || "Failed to update officer")
    } finally {
      setUpdating(false)
    }
  }

  const handleDeleteClick = (officer: OfficerOut) => {
    setSelectedOfficer(officer)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!selectedOfficer) return
    try {
      setDeleting(true)
      setError(null)
      await deleteOfficer(selectedOfficer.user_id)
      setSuccess("Officer deleted")
      setDeleteDialogOpen(false)
      setSelectedOfficer(null)
      await fetchOfficers()
    } catch (err: any) {
      setError(err.message || "Failed to delete officer")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <UserCog className="w-6 h-6 text-accent" />
            <h1 className="text-3xl font-bold">Officer Management</h1>
          </div>
          <p className="text-muted-foreground">Manage system officers and their access levels</p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} className="gap-2">
          {showCreate ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showCreate ? "Cancel" : "Add Officer"}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <CheckCircle2 className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Create form */}
      {showCreate && (
        <Card className="p-6 bg-card/50 border-border space-y-4">
          <h2 className="text-lg font-semibold">Create New Officer</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Email *</label>
              <Input
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                placeholder="officer@example.com"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Password *</label>
              <Input
                type="password"
                value={createForm.password}
                onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                placeholder="••••••"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Full Name *</label>
              <Input
                value={createForm.full_name}
                onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                placeholder="John Doe"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Rank</label>
              <Input
                value={createForm.rank}
                onChange={(e) => setCreateForm({ ...createForm, rank: e.target.value })}
                placeholder="e.g. Sergeant"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">ID Number *</label>
              <Input
                value={createForm.id_number}
                onChange={(e) => setCreateForm({ ...createForm, id_number: e.target.value })}
                placeholder="ID-12345"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Work Station</label>
              <Input
                value={createForm.work_station}
                onChange={(e) => setCreateForm({ ...createForm, work_station: e.target.value })}
                placeholder="e.g. airport, harbour, border"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Access Type</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setCreateForm({ ...createForm, access_type: "verify_only" })}
                  className={`flex-1 px-3 py-2 rounded-md text-xs font-medium border transition-colors ${
                    createForm.access_type === "verify_only"
                      ? "bg-accent/20 border-accent/50 text-accent"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  Verify Only
                </button>
                <button
                  type="button"
                  onClick={() => setCreateForm({ ...createForm, access_type: "register_and_verify" })}
                  className={`flex-1 px-3 py-2 rounded-md text-xs font-medium border transition-colors ${
                    createForm.access_type === "register_and_verify"
                      ? "bg-accent/20 border-accent/50 text-accent"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  Register & Verify
                </button>
              </div>
            </div>
          </div>
          <Button onClick={handleCreate} disabled={creating} className="w-full sm:w-auto">
            {creating ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Creating...</>
            ) : (
              "Create Officer"
            )}
          </Button>
        </Card>
      )}

      {/* Officers table */}
      <Card className="bg-card/50 border-border p-6">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-muted rounded animate-pulse" />
            ))}
          </div>
        ) : officers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-sm font-semibold">Name</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Email</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Station</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Access</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {officers.map((officer) => (
                  <tr key={officer.user_id} className="border-b border-border/50 hover:bg-background/50">
                    {editingId === officer.user_id ? (
                      <>
                        <td className="py-3 px-4">
                          <Input
                            value={editForm.full_name || ""}
                            onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                            className="h-8 text-sm"
                          />
                        </td>
                        <td className="py-3 px-4 text-sm text-muted-foreground">{officer.email}</td>
                        <td className="py-3 px-4">
                          <Input
                            value={editForm.work_station || ""}
                            onChange={(e) => setEditForm({ ...editForm, work_station: e.target.value })}
                            className="h-8 text-sm"
                          />
                        </td>
                        <td className="py-3 px-4">
                          <select
                            value={editForm.access_type || "verify_only"}
                            onChange={(e) =>
                              setEditForm({
                                ...editForm,
                                access_type: e.target.value as "register_and_verify" | "verify_only",
                              })
                            }
                            className="h-8 text-sm rounded border border-border bg-background px-2"
                          >
                            <option value="verify_only">Verify Only</option>
                            <option value="register_and_verify">Register & Verify</option>
                          </select>
                        </td>
                        <td className="py-3 px-4">
                          <button
                            type="button"
                            onClick={() =>
                              setEditForm({ ...editForm, is_active: !editForm.is_active })
                            }
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              editForm.is_active
                                ? "bg-green-500/20 text-green-500"
                                : "bg-red-500/20 text-red-500"
                            }`}
                          >
                            {editForm.is_active ? "Active" : "Inactive"}
                          </button>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex gap-1">
                            <Button size="sm" onClick={handleUpdate} disabled={updating}>
                              {updating ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save"}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                              Cancel
                            </Button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-3 px-4">
                          <div>
                            <span className="font-medium">{officer.full_name}</span>
                            {officer.rank && (
                              <span className="text-xs text-muted-foreground ml-2">({officer.rank})</span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground">{officer.id_number}</span>
                        </td>
                        <td className="py-3 px-4 text-sm">{officer.email}</td>
                        <td className="py-3 px-4 text-sm">{officer.work_station || "-"}</td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-500 border-blue-500/30">
                              Match
                            </Badge>
                            {officer.access_type === "register_and_verify" && (
                              <Badge variant="outline" className="text-xs bg-green-500/10 text-green-500 border-green-500/30">
                                Enroll
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <Badge
                            variant={officer.is_active ? "default" : "destructive"}
                            className={`text-xs ${officer.is_active ? "bg-green-500/20 text-green-500 border-green-500/30" : ""}`}
                          >
                            {officer.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => startEdit(officer)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteClick(officer)}
                              className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No officers registered yet</p>
            <p className="text-xs text-muted-foreground mt-2">Click "Add Officer" to create one</p>
          </div>
        )}
      </Card>

      <DeleteDialog
        isOpen={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete Officer"
        description={`Are you sure you want to delete ${selectedOfficer?.full_name} (${selectedOfficer?.email})? This action cannot be undone.`}
        isLoading={deleting}
        onConfirm={handleConfirmDelete}
      />
    </div>
  )
}
