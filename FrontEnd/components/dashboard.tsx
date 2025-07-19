"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { io, type Socket } from "socket.io-client"
import { MapContainer } from "@/components/map-container"
import { TaxiTable } from "@/components/taxi-table"
import { BaseTable } from "@/components/base-table"
import { RequestTable } from "@/components/request-table"
import { BaseActivityLog } from "@/components/base-activity-log"
import { ViolationLog } from "@/components/violation-log"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { LogOut } from "lucide-react"
import { WEBSOCKET_URL} from "@/lib/config"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export interface TaxiState {
  taxi_state: string
  latitude: number
  longitude: number
  battery: number
}

export interface BaseState {
  latitude: number
  longitude: number
  fleet: (number | null)[]
}

export interface Assignment {
  base_id: string
  polyline: string
  deviate_radius?: number
}

export interface BaseActivityLogEntry {
  timestamp: string
  base_id: string
  status: string
  taxi_id: string | number
}

export interface ViolationLogEntry {
  timestamp: string
  taxi_id: string | number
  base_id: string
  reason: string
}

export function Dashboard() {
  const router = useRouter()
  const [socket, setSocket] = useState<Socket | null>(null)
  const [taxiStates, setTaxiStates] = useState<Record<string, TaxiState>>({})
  const [baseStates, setBaseStates] = useState<Record<string, BaseState>>({})
  const [baseRequests, setBaseRequests] = useState<string[]>([])
  const [baseActivityLogs, setBaseActivityLogs] = useState<BaseActivityLogEntry[]>([])
  const [violationLogs, setViolationLogs] = useState<ViolationLogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem("token")
    if (!token) {
      router.push("/")
      return
    }


    if (!WEBSOCKET_URL) {
      setError("WebSocket URL is not configured")
      return
    }

    try {
      const socketInstance = io(WEBSOCKET_URL, {
        transports: ["websocket", "polling"],
        auth: {
          token,
        },
        withCredentials: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        timeout: 20000,
      })

      socketInstance.on("connect", () => {
        setConnected(true)
        setError(null)
        socketInstance.emit("operator_register")
      })

      socketInstance.on("connect_error", (err) => {
        setError(`Error connection websocket: ${err.message}`)
        setConnected(false)
      })

      socketInstance.on("disconnect", () => {
        setConnected(false)
      })

      socketInstance.on("initial_data", (data) => {
        console.log("Received initial data:", data)
        setTaxiStates(data.taxi_states || {})
        setBaseStates(data.base_states || {})

        if (data.log_base_activity) {
          const baseActivityLogsArray = Object.entries(data.log_base_activity).map(
            ([timestamp, log]: [string, any]) => ({
              timestamp,
              ...log,
            }),
          )
          setBaseActivityLogs(baseActivityLogsArray)
        }

        if (data.log_pelanggaran_data) {
          const violationLogsArray = Object.entries(data.log_pelanggaran_data).map(
            ([timestamp, log]: [string, any]) => ({
              timestamp,
              ...log,
            }),
          )
          setViolationLogs(violationLogsArray)
        }
      })

      socketInstance.on("update_data", (data) => {
        console.log("Received update data:", data)
        setTaxiStates(data.taxi_states || {})
        setBaseStates(data.base_states || {})
        setBaseRequests(data.base_requests || [])

        if (data.log_base_activity) {
          const baseActivityLogsArray = Object.entries(data.log_base_activity).map(
            ([timestamp, log]: [string, any]) => ({
              timestamp,
              ...log,
            }),
          )
          setBaseActivityLogs(baseActivityLogsArray)
        }

        if (data.log_pelanggaran_data) {
          const violationLogsArray = Object.entries(data.log_pelanggaran_data).map(
            ([timestamp, log]: [string, any]) => ({
              timestamp,
              ...log,
            }),
          )
          setViolationLogs(violationLogsArray)
        }
      })

      setSocket(socketInstance)

      return () => {
        socketInstance.disconnect()
      }
    } catch (err) {
      console.error("Error setting up WebSocket:", err)
      setError("Failed to initialize WebSocket connection")
    }
  }, [router])

  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("userId")
    if (socket) {
      socket.disconnect()
    }
    router.push("/")
  }

  return (
    <div className="min-h-screen flex flex-col">


      <header className="bg-blue-600 text-white p-4 flex justify-between items-center">
        <h1 className="text-2xl font-bold">BlueBird</h1>
        <div className="flex items-center gap-4">
          <span className={`inline-block w-3 h-3 rounded-full ${connected ? "bg-green-400" : "bg-red-500"}`}></span>
          <span>{connected ? "Connected" : "Disconnected"}</span>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </Button>
        </div>
      </header>



      <main className="flex-1 p-4 flex flex-col gap-4">
        <div className="h-[500px] bg-white rounded-lg shadow-md overflow-hidden relative z-0">
          <MapContainer taxiStates={taxiStates} baseStates={baseStates} />
        </div>

        <Tabs defaultValue="taxis" className="bg-white rounded-lg shadow-md p-4">
          <TabsList className="grid grid-cols-4 mb-4">
            <TabsTrigger value="taxis">Taxis</TabsTrigger>
            <TabsTrigger value="bases">Bases</TabsTrigger>
            <TabsTrigger value="activity-logs">Base Activity Logs</TabsTrigger>
            <TabsTrigger value="violation-logs">Violation Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="taxis">
            <TaxiTable taxiStates={taxiStates} />
          </TabsContent>

          <TabsContent value="bases">
            <BaseTable baseStates={baseStates} />
          </TabsContent>
          <TabsContent value="activity-logs">
            <BaseActivityLog logs={baseActivityLogs} />
          </TabsContent>

          <TabsContent value="violation-logs">
            <ViolationLog logs={violationLogs} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
