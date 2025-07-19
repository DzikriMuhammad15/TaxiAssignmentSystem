"use client"

import type { BaseState } from "./dashboard"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

interface RequestTableProps {
  baseRequests: string[]
  baseStates: Record<string, BaseState>
}

export function RequestTable({ baseRequests, baseStates }: RequestTableProps) {
  const requestCounts = baseRequests.reduce(
    (acc, baseId) => {
      acc[baseId] = (acc[baseId] || 0) + 1
      return acc
    },
    {} as Record<string, number>,
  )

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Base ID</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Requested Taxis</TableHead>
            <TableHead>Available Slots</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.keys(requestCounts).length > 0 ? (
            Object.entries(requestCounts).map(([baseId, count]) => {
              const baseState = baseStates[baseId]
              const availableSlots = baseState ? baseState.fleet.filter((slot) => slot === null).length : "Unknown"

              return (
                <TableRow key={baseId}>
                  <TableCell className="font-medium">{baseId}</TableCell>
                  <TableCell>
                    {baseState ? `${baseState.latitude.toFixed(6)}, ${baseState.longitude.toFixed(6)}` : "Unknown"}
                  </TableCell>
                  <TableCell>{count}</TableCell>
                  <TableCell>{availableSlots}</TableCell>
                </TableRow>
              )
            })
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center">
                No base requests
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
