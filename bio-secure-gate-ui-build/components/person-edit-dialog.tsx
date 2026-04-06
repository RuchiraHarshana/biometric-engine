"use client"
import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { getStoredUser } from "@/lib/auth"

export function PersonEditDialog({ open, onOpenChange, person, onSave, loading, error }) {
  const user = getStoredUser()
  const isAdmin = user?.role === "admin"

  // Non-admin users cannot edit enrolled persons
  const isEnrolled = person.has_face || person.has_fingerprint
  const canEdit = isAdmin || !isEnrolled

  const [fullName, setFullName] = useState(person.full_name || "")
  const [email, setEmail] = useState(person.email || "")
  const [mobileNumber, setMobileNumber] = useState(person.mobile_number || "")
  const [address, setAddress] = useState(person.address || "")
  const [criminalRecords, setCriminalRecords] = useState(person.criminal_records || "")

  // Sync state with person prop
  useEffect(() => {
    setFullName(person.full_name || "")
    setEmail(person.email || "")
    setMobileNumber(person.mobile_number || "")
    setAddress(person.address || "")
    setCriminalRecords(person.criminal_records || "")
  }, [person])

  // Track changes
  const [touched, setTouched] = useState(false)
  function handleChange(setter) {
    setTouched(true)
    return setter
  }

  function handleSubmit(e) {
    e.preventDefault()
    const updates = {}
    if (fullName !== person.full_name) updates.full_name = fullName
    if (email !== person.email) updates.email = email
    if (mobileNumber !== person.mobile_number) updates.mobile_number = mobileNumber
    if (address !== person.address) updates.address = address
    if (isAdmin && criminalRecords !== person.criminal_records) updates.criminal_records = criminalRecords
    onSave(updates)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Person</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {!canEdit && (
            <Alert variant="destructive">
              <AlertDescription>Only administrators can edit enrolled persons.</AlertDescription>
            </Alert>
          )}
          <Input label="Full Name" value={fullName} onChange={e => handleChange(setFullName)(e.target.value)} required disabled={!canEdit} />
          <Input label="Email" value={email} onChange={e => handleChange(setEmail)(e.target.value)} type="email" required disabled={!canEdit} />
          <Input label="Mobile Number" value={mobileNumber} onChange={e => handleChange(setMobileNumber)(e.target.value)} minLength={10} maxLength={15} required disabled={!canEdit} />
          <Textarea label="Address" value={address} onChange={e => handleChange(setAddress)(e.target.value)} disabled={!canEdit} />
          {isAdmin ? (
            <Textarea label="Criminal Records" value={criminalRecords} onChange={e => handleChange(setCriminalRecords)(e.target.value)} />
          ) : (
            <Textarea label="Criminal Records" value={criminalRecords} readOnly disabled />
          )}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !touched || !canEdit}>
              {loading ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
