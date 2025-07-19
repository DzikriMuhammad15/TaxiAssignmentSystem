"use client"

import type { Assignment, BaseState, TaxiState } from "./dashboard"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

interface AssignmentTableProps {
  activeAssignments: Record<string, Assignment>
  taxiStates: Record<string, TaxiState>
  baseStates: Record<string, BaseState>
}

export function AssignmentTable({ activeAssignments, taxiStates, baseStates }: AssignmentTableProps) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Taxi ID</TableHead>
            <TableHead>Taxi Status</TableHead>
            <TableHead>Assigned Base</TableHead>
            <TableHead>Taxi Location</TableHead>
            <TableHead>Base Location</TableHead>
            <TableHead>Deviation Radius</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(activeAssignments).length > 0 ? (
            Object.entries(activeAssignments).map(([taxiId, assignment]) => {
              const taxiState = taxiStates[taxiId]
              const baseState = baseStates[assignment.base_id]
              const deviateRadius = assignment.deviate_radius || 2000 

              return (
                <TableRow key={taxiId}>
                  <TableCell className="font-medium">{taxiId}</TableCell>
                  <TableCell>
                    {taxiState && (
                      <Badge
                        className={
                          taxiState.taxi_state === "kosong"
                            ? "bg-green-500"
                            : taxiState.taxi_state === "menuju penumpang"
                              ? "bg-yellow-500"
                              : "bg-red-500"
                        }
                      >
                        {taxiState.taxi_state}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{assignment.base_id}</TableCell>
                  <TableCell>
                    {taxiState ? `${taxiState.latitude.toFixed(6)}, ${taxiState.longitude.toFixed(6)}` : "Unknown"}
                  </TableCell>
                  <TableCell>
                    {baseState ? `${baseState.latitude.toFixed(6)}, ${baseState.longitude.toFixed(6)}` : "Unknown"}
                  </TableCell>
                  <TableCell>{deviateRadius} meters</TableCell>
                </TableRow>
              )
            })
          ) : (
            <TableRow>
              <TableCell colSpan={6} className="text-center">
                No active assignments
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
