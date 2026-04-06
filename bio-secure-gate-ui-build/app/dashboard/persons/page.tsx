"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, Trash2, Users } from "lucide-react"
import { getPersons, deletePerson, updatePerson } from "@/lib/api"
import { isAdmin } from "@/lib/auth"
import { API_ENDPOINTS } from "@/lib/api-config"
import { DeleteDialog } from "@/components/delete-dialog"
import { PersonEditDialog } from "@/components/person-edit-dialog"

interface Person {
  person_id: string
  full_name: string
  email?: string
  mobile_number?: string
  address?: string
  criminal_records?: string
  has_face: boolean
  has_fingerprint: boolean
  face_image_url?: string
}

export default function PersonsPage() {
  const router = useRouter()
  const [persons, setPersons] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [search, setSearch] = useState("")

  const handleEditClick = (person: Person) => {
    setSelectedPerson(person)
    setEditDialogOpen(true)
    setEditError(null)
  }

  const handleEditSave = async (updates: Record<string, any>) => {
    if (!selectedPerson) return
    setEditLoading(true)
    setEditError(null)
    try {
      const res = await updatePerson(selectedPerson.person_id, updates)
      if (res && res.person) {
        setPersons(persons.map(p => p.person_id === res.person.person_id ? res.person : p))
        setEditDialogOpen(false)
        setSelectedPerson(null)
      } else {
        setEditError("Unexpected response from server.")
      }
    } catch (err: any) {
      setEditError(err.message || "Failed to update person.")
    } finally {
      setEditLoading(false)
    }
  }

  useEffect(() => {
    if (!isAdmin()) {
      router.replace("/dashboard")
      return
    }
    fetchPersons()
  }, [router])

  const fetchPersons = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getPersons()
      if (Array.isArray(data)) {
        setPersons(data)
      } else {
        setError("Invalid response format")
      }
    } catch (err: any) {
      setError(err.message || "Failed to fetch persons.")
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteClick = (person: Person) => {
    setSelectedPerson(person)
    setDeleteDialogOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!selectedPerson) return
    try {
      setDeleteLoading(true)
      await deletePerson(selectedPerson.person_id)
      setPersons(persons.filter((p) => p.person_id !== selectedPerson.person_id))
      setDeleteDialogOpen(false)
      setSelectedPerson(null)
    } catch (err: any) {
      setError(err.message || "Failed to delete person")
    } finally {
      setDeleteLoading(false)
    }
  }

  // Filter persons by search query (person_id)
  const filteredPersons = search.trim() === ""
    ? persons
    : persons.filter((p) => p.person_id.toLowerCase().includes(search.trim().toLowerCase()))

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Users className="w-6 h-6 text-accent" />
          <h1 className="text-3xl font-bold">Persons / Criminals</h1>
        </div>
        <p className="text-muted-foreground">View and manage enrolled persons (Admin only)</p>
      </div>

      {/* Search bar */}
      <div className="mb-4 flex items-center gap-2">
        <input
          type="text"
          placeholder="Search by Person ID..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full max-w-xs px-3 py-2 border border-border rounded focus:outline-none focus:ring-2 focus:ring-accent"
        />
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="bg-card/50 border-border p-6">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 bg-muted rounded animate-pulse" />
            ))}
          </div>
        ) : filteredPersons.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-sm font-semibold">Person ID</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Full Name</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Face Enrolled</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Fingerprint Enrolled</th>
                  <th className="text-left py-3 px-4 text-sm font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredPersons.map((person) => (
                  <tr
                    key={person.person_id}
                    className="border-b border-border/50 hover:bg-background/50 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <code className="text-xs bg-background/50 px-2 py-1 rounded">{person.person_id}</code>
                    </td>
                    <td className="py-3 px-4 font-medium">{person.full_name}</td>
                    <td className="py-3 px-4">
                      {person.has_face ? <Badge variant="secondary">Yes</Badge> : <Badge variant="outline">No</Badge>}
                    </td>
                    <td className="py-3 px-4">
                      {person.has_fingerprint ? (
                        <Badge variant="secondary">Yes</Badge>
                      ) : (
                        <Badge variant="outline">No</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEditClick(person)}
                        className="text-accent"
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteClick(person)}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                        <PersonEditDialog
                          open={editDialogOpen}
                          onOpenChange={setEditDialogOpen}
                          person={selectedPerson || {}}
                          onSave={handleEditSave}
                          loading={editLoading}
                          error={editError}
                        />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No persons enrolled yet</p>
            <p className="text-xs text-muted-foreground mt-2">Start by enrolling face or fingerprint data</p>
          </div>
        )}
      </Card>

      <DeleteDialog
        isOpen={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete Person"
        description={`Are you sure you want to delete ${selectedPerson?.full_name} (${selectedPerson?.person_id})? This action cannot be undone.`}
        isLoading={deleteLoading}
        onConfirm={handleConfirmDelete}
      />
    </div>
  )
}
