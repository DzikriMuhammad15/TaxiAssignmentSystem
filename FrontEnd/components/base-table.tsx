"use client"

import type { BaseState } from "./dashboard"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Progress } from "@/components/ui/progress"

interface BaseTableProps {
  baseStates: Record<string, BaseState>
}

export function BaseTable({ baseStates }: BaseTableProps) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Base ID</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Capacity</TableHead>
            <TableHead>Occupancy</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(baseStates).length > 0 ? (
            Object.entries(baseStates).map(([baseId, state]) => {
              const occupiedSlots = state.fleet.filter((slot) => slot !== null).length
              const totalSlots = state.fleet.length
              const occupancyPercentage = (occupiedSlots / totalSlots) * 100

              return (
                <TableRow key={baseId}>
                  <TableCell className="font-medium">{baseId}</TableCell>
                  <TableCell>
                    {state.latitude.toFixed(6)}, {state.longitude.toFixed(6)}
                  </TableCell>
                  <TableCell>{totalSlots}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress value={occupancyPercentage} className="h-2" />
                      <span className="text-sm">
                        {occupiedSlots}/{totalSlots}
                      </span>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center">
                No base data available
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
