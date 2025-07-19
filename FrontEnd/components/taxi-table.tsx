"use client"

import type { TaxiState } from "./dashboard"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

interface TaxiTableProps {
  taxiStates: Record<string, TaxiState>
}

export function TaxiTable({ taxiStates }: TaxiTableProps) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Taxi ID</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Battery</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(taxiStates).length > 0 ? (
            Object.entries(taxiStates).map(([taxiId, state]) => (
              <TableRow key={taxiId}>
                <TableCell className="font-medium">{taxiId}</TableCell>
                <TableCell>
                  <Badge
                    className={
                      state.taxi_state === "kosong"
                        ? "bg-green-500"
                        : state.taxi_state === "menuju penumpang"
                          ? "bg-yellow-500"
                          : "bg-red-500"
                    }
                  >
                    {state.taxi_state}
                  </Badge>
                </TableCell>
                <TableCell>
                  {state.latitude.toFixed(6)}, {state.longitude.toFixed(6)}
                </TableCell>
                <TableCell>{state.battery}%</TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4} className="text-center">
                No taxi data available
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
